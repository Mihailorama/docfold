"""Engine router — selects and invokes the best engine for a given document."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.utils.quality import strip_base64_images

logger = logging.getLogger(__name__)

QualityGate = Callable[[EngineResult, str], "str | None"]
"""``gate(result, file_path)`` returns a rejection reason, or ``None`` to accept."""

FallbackPlan = Callable[
    ["EngineResult | None", str], "list[str] | tuple[list[str], dict[str, Any]]"
]
"""``plan(primary_result_or_None, file_path)`` -> engines, or ``(engines, info)``.

Called only when the primary attempt fails; ``info`` is merged into the
primary ``fallback_chain`` record (e.g. ``script_hint``). See
:class:`docfold.utils.script.ScriptRouting`.
"""

# ---------------------------------------------------------------------------
# Extension-aware priority map
# ---------------------------------------------------------------------------
# Each file extension maps to an ordered list of engine names that are
# most appropriate for that format.  The router walks this list and picks
# the first *available* engine that supports the extension.

_IMAGE_PRIORITY = [
    "chandra", "unlimited_ocr", "surya", "paddleocr", "tesseract", "easyocr",
    "docling", "liteparse", "mistral_ocr", "google_docai", "textract",
    "azure_docint", "zerox", "marker", "markitdown",
]

_EXTENSION_PRIORITY: dict[str, list[str]] = {
    # --- PDF ---
    "pdf": [
        "docling", "mineru", "chandra", "unlimited_ocr", "unstructured", "marker",
        "modal_marker", "llamaparse", "liteparse", "mistral_ocr", "firecrawl", "google_docai",
        "azure_docint", "textract", "zerox", "nougat", "surya", "pymupdf",
        "paddleocr", "tesseract", "easyocr", "markitdown",
    ],
    # --- Office ---
    "docx": [
        "docling", "marker", "unstructured", "llamaparse",
        "liteparse", "firecrawl", "azure_docint", "markitdown",
    ],
    "doc":  ["docling", "marker", "unstructured", "llamaparse", "liteparse", "azure_docint"],
    "pptx": [
        "docling", "marker", "unstructured", "llamaparse",
        "liteparse", "azure_docint", "markitdown",
    ],
    "ppt":  ["docling", "marker", "unstructured", "llamaparse", "liteparse", "azure_docint"],
    "xlsx": [
        "docling", "marker", "unstructured", "llamaparse",
        "liteparse", "azure_docint", "markitdown", "spreadsheet",
    ],
    "xlsm": ["spreadsheet"],
    "xls":  [
        "docling", "marker", "unstructured", "llamaparse",
        "liteparse", "azure_docint", "markitdown",
    ],
    "odt":  ["marker", "unstructured"],
    "odp":  ["marker", "unstructured"],
    "ods":  ["marker", "unstructured"],
    # --- Web / markup ---
    "html": ["docling", "firecrawl", "unstructured", "marker", "azure_docint", "markitdown"],
    "htm":  ["docling", "firecrawl", "unstructured", "marker", "azure_docint", "markitdown"],
    "xml":  ["firecrawl", "unstructured", "markitdown"],
    "md":   ["unstructured", "markitdown"],
    "rst":  ["unstructured"],
    "csv":  ["unstructured", "markitdown", "spreadsheet"],
    "tsv":  ["unstructured", "markitdown", "spreadsheet"],
    "txt":  ["unstructured", "markitdown"],
    "rtf":  ["unstructured"],
    "json": ["markitdown"],
    # --- Images ---
    "png":  _IMAGE_PRIORITY,
    "jpg":  _IMAGE_PRIORITY,
    "jpeg": _IMAGE_PRIORITY,
    "tiff": _IMAGE_PRIORITY,
    "tif":  _IMAGE_PRIORITY,
    "bmp":  _IMAGE_PRIORITY,
    "webp": _IMAGE_PRIORITY,
    "gif":  ["google_docai"],
    # --- Email ---
    "eml":  ["unstructured"],
    "msg":  ["unstructured"],
    # --- eBooks ---
    "epub": ["unstructured", "marker", "markitdown"],
    # --- Audio (transcription) ---
    "mp3": ["markitdown", "whisper"],
    "wav": ["markitdown", "whisper"],
    "m4a": ["markitdown", "whisper"],
    # --- Archives ---
    "zip": ["markitdown"],
}

# Ultimate fallback when extension is unknown or missing from the map.
_DEFAULT_FALLBACK = [
    "docling", "mineru", "chandra", "unlimited_ocr", "unstructured", "marker",
    "llamaparse", "liteparse", "mistral_ocr", "google_docai", "azure_docint",
    "textract", "zerox", "nougat", "surya", "pymupdf", "paddleocr", "tesseract",
    "easyocr", "markitdown",
]


# ------------------------------------------------------------------
# Progress callback protocol
# ------------------------------------------------------------------

class ProgressCallback(Protocol):
    """Protocol for progress reporting.

    Implement this to get notified about batch processing progress.
    Compatible with any callable that accepts these keyword args.
    """

    def __call__(
        self,
        *,
        current: int,
        total: int,
        file_path: str,
        engine_name: str,
        status: str,
        result: EngineResult | None = None,
        error: Exception | None = None,
    ) -> None: ...


@dataclass
class BatchResult:
    """Result of a batch processing run."""

    results: dict[str, EngineResult] = field(default_factory=dict)
    """Mapping of file_path → EngineResult for successful files."""

    errors: dict[str, str] = field(default_factory=dict)
    """Mapping of file_path → error message for failed files."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    total_time_ms: int = 0

    @property
    def success_rate(self) -> float:
        return self.succeeded / self.total if self.total > 0 else 0.0


class EngineRouter:
    """Central entry-point for document processing.

    Maintains a registry of available engines and selects the most
    appropriate one for each request based on:

    1. Explicit ``engine`` hint from the caller.
    2. ``ENGINE_DEFAULT`` environment variable.
    3. Extension-aware priority chain (or user-provided ``fallback_order``).
    4. ``allowed_engines`` filter (if set).
    """

    def __init__(
        self,
        engines: list[DocumentEngine] | None = None,
        fallback_order: list[str] | None = None,
        allowed_engines: set[str] | None = None,
    ) -> None:
        self._engines: dict[str, DocumentEngine] = {}
        self._fallback_order = fallback_order
        self._allowed_engines = allowed_engines
        for engine in engines or []:
            self.register(engine)

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------

    def register(self, engine: DocumentEngine) -> None:
        """Add an engine to the registry."""
        self._engines[engine.name] = engine
        logger.info("Registered engine: %s (available=%s)", engine.name, engine.is_available())

    def get(self, name: str) -> DocumentEngine | None:
        return self._engines.get(name)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _get_priority(self, ext: str) -> list[str]:
        """Return the engine priority list for *ext*."""
        if self._fallback_order is not None:
            return self._fallback_order
        return _EXTENSION_PRIORITY.get(ext, _DEFAULT_FALLBACK)

    def _is_candidate(self, engine: DocumentEngine, ext: str) -> bool:
        """Check if *engine* is available and passes the allowed filter."""
        if not engine.is_available():
            return False
        if self._allowed_engines and engine.name not in self._allowed_engines:
            return False
        if ext and ext not in engine.supported_extensions:
            return False
        return True

    def select(
        self,
        file_path: str,
        engine_hint: str | None = None,
        **kwargs: Any,
    ) -> DocumentEngine:
        """Choose the best engine for *file_path*.

        Raises ``ValueError`` if no suitable engine is found.
        """
        ext = Path(file_path).suffix.lstrip(".").lower()

        # 1. Explicit hint
        if engine_hint:
            engine = self._engines.get(engine_hint)
            if engine is None:
                available = ", ".join(self._engines)
                raise ValueError(
                    f"Unknown engine '{engine_hint}'. Available: {available}"
                )
            if not engine.is_available():
                raise RuntimeError(f"Engine '{engine_hint}' is registered but not available.")
            if ext and ext not in engine.supported_extensions:
                logger.warning(
                    "Engine '%s' does not list '.%s' as supported — proceeding anyway.",
                    engine_hint,
                    ext,
                )
            return engine

        # 2. Environment default
        env_default = os.getenv("ENGINE_DEFAULT")
        if env_default:
            engine = self._engines.get(env_default)
            if engine and self._is_candidate(engine, ext):
                return engine

        # 3. Extension-aware priority chain
        for name in self._get_priority(ext):
            engine = self._engines.get(name)
            if engine and self._is_candidate(engine, ext):
                return engine

        # 4. Any available engine that supports the extension
        for engine in self._engines.values():
            if self._is_candidate(engine, ext):
                return engine

        raise ValueError(
            f"No available engine supports '.{ext}'. "
            f"Registered: {list(self._engines.keys())}"
        )

    # ------------------------------------------------------------------
    # Single-file processing
    # ------------------------------------------------------------------

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        engine_hint: str | None = None,
        *,
        quality_gate: QualityGate | None = None,
        fallback_engines: list[str] | FallbackPlan | None = None,
        supplement_engine: str | None = None,
        **kwargs: Any,
    ) -> EngineResult:
        """Select an engine and process the document.

        If the selected engine fails and no explicit ``engine_hint`` was
        given, the router automatically tries the remaining engines from the
        priority chain before raising an error.

        Args:
            quality_gate: ``gate(result, file_path) -> reason | None``. A
                result with a reason is rejected and the next engine runs; a
                later result is accepted when it passes the gate and has more
                real text than every earlier attempt. If no attempt passes,
                the one with the most real text is returned. See
                :func:`docfold.utils.quality.default_quality_gate`.
            fallback_engines: Explicit retry order after the primary engine
                (the hinted one, or the first by priority). Enables fallback
                even with ``engine_hint``. May be a :data:`FallbackPlan`
                callable, evaluated only when the primary attempt fails.
            supplement_engine: Engine run after the primary result is chosen
                (unless it produced it) to add layout: its ``bounding_boxes``,
                ``images`` and ``metadata`` are merged into the result, the
                primary text is kept. Failures never fail the call.

        Every attempt is recorded in ``result.fallback_chain``.
        """
        result = await self._process_chain(
            file_path, output_format, engine_hint,
            quality_gate=quality_gate, fallback_engines=fallback_engines, **kwargs,
        )
        if supplement_engine and supplement_engine != result.engine_name:
            result = await self._supplement(
                result, supplement_engine, file_path, output_format, **kwargs
            )
        return result

    async def _process_chain(
        self,
        file_path: str,
        output_format: OutputFormat,
        engine_hint: str | None,
        *,
        quality_gate: QualityGate | None,
        fallback_engines: list[str] | FallbackPlan | None,
        **kwargs: Any,
    ) -> EngineResult:
        ext = Path(file_path).suffix.lstrip(".").lower()
        chain: list[dict[str, Any]] = []
        names: list[str]
        plan: FallbackPlan | None = None
        static: list[str] | None = None
        if callable(fallback_engines):
            plan = fallback_engines
        else:
            static = fallback_engines

        if engine_hint:
            # Validates the hint (raises on unknown / unavailable engines).
            self.select(file_path, engine_hint=engine_hint, **kwargs)
            names = [engine_hint, *(static or [])]
        else:
            candidates = self._candidates(ext)
            if not candidates:
                raise ValueError(
                    f"No available engine supports '.{ext}'. "
                    f"Registered: {list(self._engines.keys())}"
                )
            names = (
                [candidates[0].name, *(static or [])]
                if fallback_engines is not None
                else [e.name for e in candidates]
            )

        best: EngineResult | None = None
        best_attempt: dict[str, Any] | None = None
        best_chars = -1
        errors: list[tuple[str, Exception]] = []
        tried: set[str] = set()
        primary_result: EngineResult | None = None
        planned = plan is None
        while names or not planned:
            if not names and plan is not None:
                # Primary failed: ask the plan for the retry chain once.
                planned = True
                out = plan(primary_result, file_path)
                engines, info = out if isinstance(out, tuple) else (out, {})
                chain[0].update(info)
                names = list(engines)
                continue
            name = names.pop(0)
            if name in tried:
                continue
            tried.add(name)
            attempt: dict[str, Any] = {
                "engine": name, "chars": 0, "confidence": None, "processing_time_ms": 0,
                "selected": False, "role": "fallback" if chain else "primary",
            }
            chain.append(attempt)
            engine = self._engines.get(name)
            if engine is None or not engine.is_available():
                attempt["skip_reason"] = "engine_unavailable"
                continue
            try:
                logger.info("Processing '%s' with engine '%s'", file_path, name)
                result = await engine.process(file_path, output_format=output_format, **kwargs)
            except Exception as exc:
                if engine_hint and not fallback_engines:
                    raise  # explicit hint, no fallback requested: unchanged behaviour
                logger.warning(
                    "Engine '%s' failed on '%s': %s — trying next engine", name, file_path, exc,
                )
                attempt["error"] = str(exc)
                errors.append((name, exc))
                continue

            if len(chain) == 1:
                primary_result = result
            chars = len(strip_base64_images(result.content or "").strip())
            attempt.update(
                engine=result.engine_name or name,
                chars=chars,
                confidence=result.confidence,
                processing_time_ms=result.processing_time_ms,
            )
            reason = quality_gate(result, file_path) if quality_gate else None
            if reason:
                logger.info("Engine '%s' rejected by quality gate: %s", name, reason)
                attempt["skip_reason"] = reason
            elif chars > best_chars or best is None:
                attempt["selected"] = True
                if best_attempt is not None:
                    best_attempt["selected"] = False
                result.fallback_chain = chain
                return result
            if chars > best_chars:
                best, best_attempt, best_chars = result, attempt, chars

        if best is not None and best_attempt is not None:
            best_attempt["selected"] = True
            best.fallback_chain = chain
            return best

        err_summary = "; ".join(f"{name}: {exc}" for name, exc in errors)
        raise RuntimeError(
            f"All engines failed for '{file_path}'. Errors: {err_summary}"
        )

    async def _supplement(
        self,
        result: EngineResult,
        name: str,
        file_path: str,
        output_format: OutputFormat,
        **kwargs: Any,
    ) -> EngineResult:
        """Run *name* and graft its layout onto *result* (DOCFOLD-13)."""
        attempt: dict[str, Any] = {
            "engine": name, "chars": 0, "confidence": None, "processing_time_ms": 0,
            "selected": False, "role": "bbox_supplement",
        }
        chain = result.fallback_chain if result.fallback_chain is not None else []
        chain.append(attempt)
        result.fallback_chain = chain
        engine = self._engines.get(name)
        ext = Path(file_path).suffix.lstrip(".").lower()
        if engine is None or not engine.is_available():
            attempt["skip_reason"] = "engine_unavailable"
            return result
        if ext and ext not in engine.supported_extensions:
            attempt["skip_reason"] = "unsupported_extension"
            return result
        try:
            sup = await engine.process(file_path, output_format=output_format, **kwargs)
        except Exception as exc:
            logger.warning("Supplement engine '%s' failed on '%s': %s", name, file_path, exc)
            attempt["error"] = str(exc)
            return result
        attempt.update(
            engine=sup.engine_name or name,
            chars=len(strip_base64_images(sup.content or "").strip()),
            confidence=sup.confidence,
            processing_time_ms=sup.processing_time_ms,
        )
        if sup.bounding_boxes:
            result.bounding_boxes = sup.bounding_boxes
            result.images = sup.images or result.images
            result.tables = result.tables or sup.tables
            result.metadata = {**(result.metadata or {}), **(sup.metadata or {})}
        return result

    def _candidates(self, ext: str) -> list[DocumentEngine]:
        """Available engines for *ext*: priority chain first, then the rest."""
        candidates: list[DocumentEngine] = []
        seen: set[str] = set()
        for name in [*self._get_priority(ext), *self._engines]:
            eng = self._engines.get(name)
            if eng and eng.name not in seen and self._is_candidate(eng, ext):
                candidates.append(eng)
                seen.add(eng.name)
        return candidates

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    async def process_batch(
        self,
        file_paths: list[str],
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        engine_hint: str | None = None,
        concurrency: int = 3,
        on_progress: ProgressCallback | Callable | None = None,
        **kwargs: Any,
    ) -> BatchResult:
        """Process multiple documents with bounded concurrency.

        Args:
            file_paths: List of document paths to process.
            output_format: Desired output format for all documents.
            engine_hint: Force a specific engine for all files.
            concurrency: Max number of files processed simultaneously.
            on_progress: Callback invoked after each file completes.
                Signature: ``(current, total, file_path, engine_name, status, result?, error?)``

        Returns:
            :class:`BatchResult` with per-file results and error summary.

        Example::

            def my_progress(*, current, total, file_path, status, **_):
                print(f"[{current}/{total}] {status}: {file_path}")

            batch = await router.process_batch(
                ["a.pdf", "b.pdf", "c.docx"],
                concurrency=2,
                on_progress=my_progress,
            )
            print(f"{batch.succeeded}/{batch.total} succeeded")
        """
        start = time.perf_counter()
        semaphore = asyncio.Semaphore(concurrency)
        batch = BatchResult(total=len(file_paths))

        async def _process_one(idx: int, fp: str) -> None:
            engine_name = "unknown"
            async with semaphore:
                try:
                    engine = self.select(fp, engine_hint=engine_hint, **kwargs)
                    engine_name = engine.name

                    if on_progress:
                        on_progress(
                            current=idx + 1,
                            total=batch.total,
                            file_path=fp,
                            engine_name=engine_name,
                            status="processing",
                            result=None,
                            error=None,
                        )

                    result = await engine.process(fp, output_format=output_format, **kwargs)
                    batch.results[fp] = result
                    batch.succeeded += 1

                    if on_progress:
                        on_progress(
                            current=idx + 1,
                            total=batch.total,
                            file_path=fp,
                            engine_name=engine_name,
                            status="completed",
                            result=result,
                            error=None,
                        )

                except Exception as exc:
                    logger.exception("Batch: failed to process '%s'", fp)
                    batch.errors[fp] = str(exc)
                    batch.failed += 1

                    if on_progress:
                        on_progress(
                            current=idx + 1,
                            total=batch.total,
                            file_path=fp,
                            engine_name=engine_name,
                            status="failed",
                            result=None,
                            error=exc,
                        )

        tasks = [_process_one(i, fp) for i, fp in enumerate(file_paths)]
        await asyncio.gather(*tasks)

        batch.total_time_ms = int((time.perf_counter() - start) * 1000)
        return batch

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    async def compare(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        engines: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, EngineResult]:
        """Run the same document through multiple engines and return all results.

        If *engines* is ``None``, all available engines that support the
        file extension are used.
        """
        ext = Path(file_path).suffix.lstrip(".").lower()
        targets: list[DocumentEngine] = []

        if engines:
            for name in engines:
                e = self._engines.get(name)
                if e and e.is_available():
                    targets.append(e)
        else:
            targets = [
                e
                for e in self._engines.values()
                if e.is_available() and (not ext or ext in e.supported_extensions)
            ]

        results: dict[str, EngineResult] = {}
        for engine in targets:
            try:
                result = await engine.process(file_path, output_format=output_format, **kwargs)
                results[engine.name] = result
            except Exception:
                logger.exception("Engine '%s' failed on '%s'", engine.name, file_path)

        return results

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_engines(self) -> list[dict[str, Any]]:
        """Return metadata about all registered engines."""
        return [
            {
                "name": e.name,
                "available": e.is_available(),
                "extensions": sorted(e.supported_extensions),
                "capabilities": {
                    "bounding_boxes": e.capabilities.bounding_boxes,
                    "confidence": e.capabilities.confidence,
                    "images": e.capabilities.images,
                    "table_structure": e.capabilities.table_structure,
                    "heading_detection": e.capabilities.heading_detection,
                    "reading_order": e.capabilities.reading_order,
                },
            }
            for e in self._engines.values()
        ]

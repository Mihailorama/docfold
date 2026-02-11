"""Engine router — selects and invokes the best engine for a given document."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

# Fallback preference order when no hint is given and no default is set.
_DEFAULT_FALLBACK_ORDER = ["docling", "mineru", "marker", "pymupdf", "ocr"]


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
    2. File extension compatibility.
    3. ``ENGINE_DEFAULT`` environment variable.
    4. Built-in fallback chain.
    """

    def __init__(self, engines: list[DocumentEngine] | None = None) -> None:
        self._engines: dict[str, DocumentEngine] = {}
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
            if engine and engine.is_available() and (not ext or ext in engine.supported_extensions):
                return engine

        # 3. Fallback chain
        for name in _DEFAULT_FALLBACK_ORDER:
            engine = self._engines.get(name)
            if engine and engine.is_available() and (not ext or ext in engine.supported_extensions):
                return engine

        # 4. Any available engine that supports the extension
        for engine in self._engines.values():
            if engine.is_available() and (not ext or ext in engine.supported_extensions):
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
        **kwargs: Any,
    ) -> EngineResult:
        """Select an engine and process the document."""
        engine = self.select(file_path, engine_hint=engine_hint, **kwargs)
        logger.info("Processing '%s' with engine '%s'", file_path, engine.name)
        return await engine.process(file_path, output_format=output_format, **kwargs)

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
            }
            for e in self._engines.values()
        ]

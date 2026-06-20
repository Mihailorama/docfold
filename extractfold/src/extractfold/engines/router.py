"""Extraction router — selects and invokes the best engine for a document + schema."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from extractfold.engines.base import ExtractionEngine, ExtractionResult, Schema

logger = logging.getLogger(__name__)

# Default order in which extraction engines are tried.  Lift leads as the
# strongest open model; future engines (NuExtract, LLM structured outputs,
# LlamaExtract) slot in behind it.
_DEFAULT_PRIORITY = ["lift"]


@dataclass
class BatchExtractionResult:
    """Result of a batch extraction run."""

    results: dict[str, ExtractionResult] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    total_time_ms: int = 0

    @property
    def success_rate(self) -> float:
        return self.succeeded / self.total if self.total > 0 else 0.0


class ExtractionRouter:
    """Central entry-point for structured extraction.

    Selection order:

    1. Explicit ``engine`` hint from the caller.
    2. ``EXTRACT_ENGINE_DEFAULT`` environment variable.
    3. Priority chain (``fallback_order`` or the built-in default).
    4. ``allowed_engines`` filter (if set).
    """

    def __init__(
        self,
        engines: list[ExtractionEngine] | None = None,
        fallback_order: list[str] | None = None,
        allowed_engines: set[str] | None = None,
    ) -> None:
        self._engines: dict[str, ExtractionEngine] = {}
        self._fallback_order = fallback_order
        self._allowed_engines = allowed_engines
        for engine in engines or []:
            self.register(engine)

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    def register(self, engine: ExtractionEngine) -> None:
        self._engines[engine.name] = engine
        logger.info("Registered engine: %s (available=%s)", engine.name, engine.is_available())

    def get(self, name: str) -> ExtractionEngine | None:
        return self._engines.get(name)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _get_priority(self) -> list[str]:
        return self._fallback_order if self._fallback_order is not None else _DEFAULT_PRIORITY

    def _is_candidate(self, engine: ExtractionEngine, ext: str) -> bool:
        if not engine.is_available():
            return False
        if self._allowed_engines and engine.name not in self._allowed_engines:
            return False
        if ext and ext not in engine.supported_extensions:
            return False
        return True

    def select(self, file_path: str, engine_hint: str | None = None) -> ExtractionEngine:
        """Choose the best engine for *file_path*. Raises ``ValueError`` if none fit."""
        ext = Path(file_path).suffix.lstrip(".").lower()

        if engine_hint:
            engine = self._engines.get(engine_hint)
            if engine is None:
                raise ValueError(
                    f"Unknown engine '{engine_hint}'. Available: {', '.join(self._engines)}"
                )
            if not engine.is_available():
                raise RuntimeError(f"Engine '{engine_hint}' is registered but not available.")
            return engine

        env_default = os.getenv("EXTRACT_ENGINE_DEFAULT")
        if env_default:
            engine = self._engines.get(env_default)
            if engine and self._is_candidate(engine, ext):
                return engine

        for name in self._get_priority():
            engine = self._engines.get(name)
            if engine and self._is_candidate(engine, ext):
                return engine

        for engine in self._engines.values():
            if self._is_candidate(engine, ext):
                return engine

        raise ValueError(
            f"No available engine supports '.{ext}'. Registered: {list(self._engines)}"
        )

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    async def extract(
        self,
        file_path: str,
        schema: Schema,
        engine_hint: str | None = None,
        **kwargs: Any,
    ) -> ExtractionResult:
        """Select an engine and extract.  Falls back through the chain on failure."""
        if engine_hint:
            engine = self.select(file_path, engine_hint=engine_hint)
            logger.info("Extracting '%s' with engine '%s' (explicit)", file_path, engine.name)
            return await engine.extract(file_path, schema, **kwargs)

        ext = Path(file_path).suffix.lstrip(".").lower()
        candidates: list[ExtractionEngine] = []
        seen: set[str] = set()
        for name in self._get_priority():
            eng = self._engines.get(name)
            if eng and eng.name not in seen and self._is_candidate(eng, ext):
                candidates.append(eng)
                seen.add(eng.name)
        for eng in self._engines.values():
            if eng.name not in seen and self._is_candidate(eng, ext):
                candidates.append(eng)
                seen.add(eng.name)

        if not candidates:
            raise ValueError(
                f"No available engine supports '.{ext}'. Registered: {list(self._engines)}"
            )

        errors: list[tuple[str, Exception]] = []
        for engine in candidates:
            try:
                logger.info("Extracting '%s' with engine '%s'", file_path, engine.name)
                return await engine.extract(file_path, schema, **kwargs)
            except Exception as exc:
                logger.warning("Engine '%s' failed on '%s': %s", engine.name, file_path, exc)
                errors.append((engine.name, exc))

        err_summary = "; ".join(f"{name}: {exc}" for name, exc in errors)
        raise RuntimeError(f"All engines failed for '{file_path}'. Errors: {err_summary}")

    async def extract_batch(
        self,
        file_paths: list[str],
        schema: Schema,
        engine_hint: str | None = None,
        concurrency: int = 3,
        on_progress: Callable | None = None,
        **kwargs: Any,
    ) -> BatchExtractionResult:
        """Extract from many documents with bounded concurrency."""
        start = time.perf_counter()
        semaphore = asyncio.Semaphore(concurrency)
        batch = BatchExtractionResult(total=len(file_paths))

        async def _one(idx: int, fp: str) -> None:
            async with semaphore:
                try:
                    result = await self.extract(fp, schema, engine_hint=engine_hint, **kwargs)
                    batch.results[fp] = result
                    batch.succeeded += 1
                    status = "completed"
                    err: Exception | None = None
                except Exception as exc:
                    logger.exception("Batch: failed to extract '%s'", fp)
                    batch.errors[fp] = str(exc)
                    batch.failed += 1
                    status = "failed"
                    err = exc
                if on_progress:
                    on_progress(current=idx + 1, total=batch.total, file_path=fp,
                                status=status, error=err)

        await asyncio.gather(*(_one(i, fp) for i, fp in enumerate(file_paths)))
        batch.total_time_ms = int((time.perf_counter() - start) * 1000)
        return batch

    async def compare(
        self,
        file_path: str,
        schema: Schema,
        engines: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, ExtractionResult]:
        """Run the same document+schema through several engines and return all results."""
        ext = Path(file_path).suffix.lstrip(".").lower()
        if engines:
            targets = [e for n in engines if (e := self._engines.get(n)) and e.is_available()]
        else:
            targets = [
                e for e in self._engines.values()
                if e.is_available() and (not ext or ext in e.supported_extensions)
            ]

        results: dict[str, ExtractionResult] = {}
        for engine in targets:
            try:
                results[engine.name] = await engine.extract(file_path, schema, **kwargs)
            except Exception:
                logger.exception("Engine '%s' failed on '%s'", engine.name, file_path)
        return results

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_engines(self) -> list[dict[str, Any]]:
        return [
            {
                "name": e.name,
                "available": e.is_available(),
                "extensions": sorted(e.supported_extensions),
                "capabilities": {
                    "field_confidence": e.capabilities.field_confidence,
                    "provenance": e.capabilities.provenance,
                    "nested_schemas": e.capabilities.nested_schemas,
                    "batch": e.capabilities.batch,
                    "local": e.capabilities.local,
                    "remote": e.capabilities.remote,
                },
            }
            for e in self._engines.values()
        ]

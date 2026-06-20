"""Lift engine adapter — Datalab's open 9B structured-extraction model.

Install: ``pip install extractfold[lift]`` (pulls in ``lift-pdf``).

Lift is a 9B-parameter VLM that extracts schema-conformant JSON directly from
PDFs and images.  It reports 90.2% on Datalab's extraction benchmark, ahead of
open specialists such as NuExtract (81.5%).

Two inference backends are supported:

- **vLLM** (default): connect to a ``lift_vllm`` server.  Point at a remote
  server with the ``VLLM_API_BASE`` environment variable.
- **HuggingFace**: load the model locally (requires ``lift-pdf[hf]`` and a GPU).

See https://github.com/datalab-to/lift and https://www.datalab.to/blog/introducing-lift
"""

from __future__ import annotations

import logging
import time
from typing import Any

from extractfold.engines.base import (
    ExtractionCapabilities,
    ExtractionEngine,
    ExtractionResult,
    Schema,
    load_schema,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}


class LiftEngine(ExtractionEngine):
    """Adapter for Datalab Lift (document + JSON Schema → structured data).

    Example::

        engine = LiftEngine(method="vllm")
        result = await engine.extract("invoice.pdf", "invoice_schema.json")
        print(result.data)
    """

    def __init__(
        self,
        method: str = "vllm",
        vllm_api_base: str | None = None,
        max_output_tokens: int | None = None,
        page_range: str | None = None,
    ) -> None:
        self._method = method
        self._vllm_api_base = vllm_api_base
        self._max_output_tokens = max_output_tokens
        self._page_range = page_range
        self._model: Any = None

    @property
    def name(self) -> str:
        return "lift"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> ExtractionCapabilities:
        return ExtractionCapabilities(
            nested_schemas=True,
            batch=True,
            local=self._method == "hf",
            remote=self._method == "vllm",
        )

    def is_available(self) -> bool:
        try:
            import lift  # noqa: F401

            if self._method == "hf":
                import torch  # noqa: F401
                import transformers  # noqa: F401
            return True
        except Exception:
            return False

    async def extract(
        self,
        file_path: str,
        schema: Schema,
        **kwargs: Any,
    ) -> ExtractionResult:
        if not self.is_available():
            raise RuntimeError(
                "Lift is not available. Install it with `pip install extractfold[lift]` "
                "(add the `hf` extra for the local HuggingFace backend)."
            )

        import asyncio

        normalized = load_schema(schema)
        page_range = kwargs.get("page_range", self._page_range)
        max_output_tokens = kwargs.get("max_output_tokens", self._max_output_tokens)

        start = time.perf_counter()
        loop = asyncio.get_running_loop()
        data, raw, metadata = await loop.run_in_executor(
            None,
            self._do_extract,
            file_path,
            normalized,
            page_range,
            max_output_tokens,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return ExtractionResult(
            data=data,
            engine_name=self.name,
            schema=normalized,
            raw=raw,
            metadata={"method": self._method, **metadata},
            pages=metadata.get("page_count"),
            processing_time_ms=elapsed_ms,
        )

    def _get_model(self) -> Any:
        """Lazily build and cache a reusable ``InferenceManager``."""
        if self._model is None:
            from lift.model import InferenceManager

            kwargs: dict[str, Any] = {"method": self._method}
            if self._method == "vllm" and self._vllm_api_base:
                kwargs["vllm_api_base"] = self._vllm_api_base
            self._model = InferenceManager(**kwargs)
        return self._model

    def _do_extract(
        self,
        file_path: str,
        schema: dict[str, Any],
        page_range: str | None,
        max_output_tokens: int | None,
    ) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
        from lift import extract as lift_extract

        call_kwargs: dict[str, Any] = {"model": self._get_model()}
        if page_range is not None:
            call_kwargs["page_range"] = page_range
        if max_output_tokens is not None:
            call_kwargs["max_output_tokens"] = max_output_tokens

        result = lift_extract(file_path, schema, **call_kwargs)

        data = getattr(result, "extraction", None)
        if data is None:
            raise RuntimeError(
                f"Lift returned no extraction for '{file_path}' "
                f"(error: {getattr(result, 'error', 'unknown')})."
            )

        metadata: dict[str, Any] = {}
        for attr in ("page_count", "token_count", "error"):
            value = getattr(result, attr, None)
            if value is not None:
                metadata[attr] = value

        raw = getattr(result, "raw", None)
        return data, raw, metadata

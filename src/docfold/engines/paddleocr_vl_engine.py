"""PaddleOCR-VL engine adapter — Baidu's layout pipeline + 0.9B OCR VLM.

Install: ``pip install "paddleocr[doc-parser]>=3.7"`` plus ``paddlepaddle``.

PaddleOCR-VL reads layout elements, not whole pages: the PaddleOCR pipeline
runs PP-DocLayout locally and sends each element to the model on a vLLM /
SGLang server::

    paddleocr genai_server --model_name PaddleOCR-VL-1.6-0.9B --backend vllm --port 8080
    export DOCFOLD_PADDLEOCR_VL_URL=http://localhost:8080/v1

Separate from the ``paddleocr`` engine, which is classic text-line OCR.
Model license: Apache-2.0.
"""

from __future__ import annotations

import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat
from docfold.engines.vlm_ocr_engine import _format_output

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}


class PaddleOCRVLEngine(DocumentEngine):
    """Adapter for ``paddleocr.PaddleOCRVL`` with a remote VLM server."""

    def __init__(
        self,
        base_url: str | None = None,
        pipeline_version: str = "v1.6",
        backend: str = "vllm-server",
        model: str | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv("DOCFOLD_PADDLEOCR_VL_URL") or "").rstrip("/")
        self._pipeline_version = pipeline_version
        self._backend = backend
        self._model = model
        self._pipeline: Any = None  # paddleocr.PaddleOCRVL, created on first use

    @property
    def name(self) -> str:
        return "paddleocr_vl"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(table_structure=True, heading_detection=True, reading_order=True)

    def is_available(self) -> bool:
        if not self._base_url:
            return False
        try:
            from paddleocr import PaddleOCRVL  # noqa: F401
            return True
        except ImportError:
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        start = time.perf_counter()
        pages = await asyncio.get_running_loop().run_in_executor(None, self._predict, file_path)
        return EngineResult(
            content=_format_output(pages, output_format),
            format=output_format,
            engine_name=self.name,
            pages=len(pages),
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={"pipeline_version": self._pipeline_version, "base_url": self._base_url},
        )

    def _predict(self, file_path: str) -> list[str]:
        if self._pipeline is None:
            from paddleocr import PaddleOCRVL

            self._pipeline = PaddleOCRVL(
                pipeline_version=self._pipeline_version,
                vl_rec_backend=self._backend,
                vl_rec_server_url=self._base_url,
                vl_rec_api_model_name=self._model,
            )
        return [res.markdown["markdown_texts"] for res in self._pipeline.predict(file_path)]

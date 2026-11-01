"""GLM-OCR engine adapter — Zhipu's document parser (PP-DocLayoutV3 + 0.9B OCR VLM).

Install: ``pip install "glmocr[selfhosted]"``

GLM-OCR reads regions, not whole pages: its SDK runs layout detection
locally and sends each region to the model served by vLLM / SGLang::

    vllm serve zai-org/GLM-OCR --served-model-name glm-ocr --port 8080
    export DOCFOLD_GLM_OCR_URL=http://localhost:8080/v1

Model license: MIT.  See https://github.com/zai-org/GLM-OCR
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}


class GLMOCREngine(DocumentEngine):
    """Adapter for GLM-OCR via the ``glmocr`` SDK in self-hosted mode."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str = "glm-ocr",
        layout_device: str | None = None,
        config_path: str | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv("DOCFOLD_GLM_OCR_URL") or "").rstrip("/")
        self._model = model
        self._layout_device = layout_device
        self._config_path = config_path
        self._parser: Any = None  # glmocr.GlmOcr, created on first use

    @property
    def name(self) -> str:
        return "glm_ocr"

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
            import glmocr  # noqa: F401
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
        result = await asyncio.get_running_loop().run_in_executor(None, self._parse, file_path)
        pages = result.json_result if isinstance(result.json_result, list) else None
        if output_format == OutputFormat.JSON:
            content = json.dumps(result.json_result, ensure_ascii=False)
        else:
            content = result.markdown_result or ""
        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=len(pages) if pages is not None else None,
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={"model": self._model, "base_url": self._base_url},
        )

    def _parse(self, file_path: str) -> Any:
        if self._parser is None:
            from glmocr import GlmOcr

            self._parser = GlmOcr(
                self._config_path,
                mode="selfhosted",
                model=self._model,
                layout_device=self._layout_device,
                _dotted={"pipeline.ocr_api.api_url": f"{self._base_url}/chat/completions"},
            )
        return self._parser.parse(file_path, save_layout_visualization=False)

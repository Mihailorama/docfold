"""Zerox engine adapter — use any Vision LLM for document OCR.

Install: ``pip install docfold[zerox]``

Zerox converts document pages to images and sends them to a Vision LLM
(GPT-4o, Claude, Gemini, DeepSeek VL, etc.) for structured extraction.

Requires an API key for the chosen VLM provider.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "webp", "bmp"}


class ZeroxEngine(DocumentEngine):
    """Adapter for Zerox — model-agnostic Vision LLM OCR.

    Pages are rendered to images, sent to a VLM, and the response
    is collected as structured markdown. Supports any OpenAI-compatible
    vision model endpoint.

    See https://github.com/getomni-ai/zerox
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        provider: str = "openai",
    ) -> None:
        self._model = model
        self._provider = provider

    @property
    def name(self) -> str:
        return "zerox"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    def is_available(self) -> bool:
        try:
            import pyzerox  # noqa: F401

            return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
        except ImportError:
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()

        content, metadata = await self._run_zerox(file_path, output_format)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata=metadata,
        )

    async def _run_zerox(
        self, file_path: str, output_format: OutputFormat
    ) -> tuple[str, dict]:
        from pyzerox import zerox

        result = await zerox(
            file_path=file_path,
            model=self._model,
        )

        pages_md = [page.content for page in result.pages]
        content = "\n\n".join(pages_md)

        if output_format == OutputFormat.JSON:
            import json

            data = [
                {"page": page.page, "text": page.content}
                for page in result.pages
            ]
            content = json.dumps(data, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            html_parts = [
                f"<div class='page' data-page='{page.page}'><p>{page.content}</p></div>"
                for page in result.pages
            ]
            content = "<html><body>" + "\n".join(html_parts) + "</body></html>"

        metadata = {
            "model": self._model,
            "provider": self._provider,
            "page_count": len(result.pages),
        }
        return content, metadata

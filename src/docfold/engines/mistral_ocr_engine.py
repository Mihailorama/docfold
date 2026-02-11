"""Mistral OCR engine adapter — Vision LLM-powered document understanding.

Install: ``pip install docfold[mistral-ocr]``

Requires an API key: https://console.mistral.ai/
Set ``MISTRAL_API_KEY`` environment variable.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "webp", "bmp"}


class MistralOCREngine(DocumentEngine):
    """Adapter for Mistral's OCR API.

    Uses Mistral's document understanding capabilities via the
    ``mistral.ocr.process`` endpoint for high-quality structured
    extraction from PDFs and images.

    See https://docs.mistral.ai/capabilities/document/
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "mistral-ocr-latest",
    ) -> None:
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self._model = model

    @property
    def name(self) -> str:
        return "mistral_ocr"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(table_structure=True, heading_detection=True)

    def is_available(self) -> bool:
        try:
            import mistralai  # noqa: F401

            return bool(self._api_key)
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

        loop = asyncio.get_running_loop()
        content, metadata = await loop.run_in_executor(
            None, self._call_ocr, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata=metadata,
        )

    def _call_ocr(self, file_path: str, output_format: OutputFormat) -> tuple[str, dict]:
        from mistralai import Mistral

        client = Mistral(api_key=self._api_key)

        # Upload file and process with OCR
        with open(file_path, "rb") as f:
            file_data = {"file_name": os.path.basename(file_path), "content": f}
            uploaded = client.files.upload(file=file_data)

        ocr_response = client.ocr.process(
            model=self._model,
            document={"type": "file_id", "file_id": uploaded.id},
        )

        # Combine pages into single output
        pages_md = []
        for page in ocr_response.pages:
            pages_md.append(page.markdown)

        content = "\n\n".join(pages_md)

        if output_format == OutputFormat.JSON:
            import json

            data = [
                {"page": i + 1, "text": page.markdown}
                for i, page in enumerate(ocr_response.pages)
            ]
            content = json.dumps(data, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            html_parts = [
                f"<div class='page' data-page='{i + 1}'><p>{page.markdown}</p></div>"
                for i, page in enumerate(ocr_response.pages)
            ]
            content = "<html><body>" + "\n".join(html_parts) + "</body></html>"

        metadata = {
            "model": self._model,
            "page_count": len(ocr_response.pages),
            "file_id": uploaded.id,
        }
        return content, metadata

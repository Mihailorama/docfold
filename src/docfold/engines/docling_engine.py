"""Docling engine adapter.

Install: ``pip install docfold[docling]``
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "pptx", "xlsx", "html",
    "png", "jpg", "jpeg", "tiff", "tif",
    "wav", "mp3", "vtt",
}


class DoclingEngine(DocumentEngine):
    """Adapter for the Docling document conversion framework.

    See https://github.com/docling-project/docling
    """

    def __init__(self, pipeline: str = "standard", ocr_enabled: bool = True) -> None:
        self._pipeline = pipeline  # "standard" or "vlm"
        self._ocr_enabled = ocr_enabled
        self._converter = None

    @property
    def name(self) -> str:
        return "docling"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=True, images=True, table_structure=True,
            heading_detection=True, reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import docling  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_converter(self):  # noqa: ANN202
        """Lazy-init the Docling DocumentConverter."""
        if self._converter is None:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
        return self._converter

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        start = time.perf_counter()
        converter = self._get_converter()

        # Docling's convert() is synchronous — run in executor
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, converter.convert, file_path)

        doc = result.document

        if output_format == OutputFormat.MARKDOWN:
            content = doc.export_to_markdown()
        elif output_format == OutputFormat.HTML:
            content = doc.export_to_html()
        elif output_format == OutputFormat.JSON:
            import json
            content = json.dumps(doc.export_to_dict(), ensure_ascii=False)
        else:
            content = doc.export_to_markdown()

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata={
                "pipeline": self._pipeline,
                "ocr_enabled": self._ocr_enabled,
            },
        )

"""Unstructured engine adapter — all-in-one document ETL toolkit.

Install: ``pip install docfold[unstructured]``
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls",
    "html", "htm", "xml", "csv", "tsv", "txt", "rtf",
    "png", "jpg", "jpeg", "tiff", "tif", "bmp",
    "eml", "msg", "epub", "odt", "rst", "md",
}


class UnstructuredEngine(DocumentEngine):
    """Adapter for the Unstructured library.

    Unstructured wraps multiple backends (Tesseract, PaddleOCR, detectron2)
    and provides a unified ``partition()`` interface with configurable
    strategies: "auto", "fast", "hi_res", "ocr_only".

    See https://github.com/Unstructured-IO/unstructured
    """

    def __init__(self, strategy: str = "auto") -> None:
        self._strategy = strategy

    @property
    def name(self) -> str:
        return "unstructured"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(table_structure=True, heading_detection=True)

    def is_available(self) -> bool:
        try:
            import unstructured  # noqa: F401

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

        loop = asyncio.get_running_loop()
        content, metadata = await loop.run_in_executor(
            None, self._extract, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata=metadata,
        )

    def _extract(self, file_path: str, output_format: OutputFormat) -> tuple[str, dict]:
        from unstructured.partition.auto import partition

        elements = partition(filename=file_path, strategy=self._strategy)

        if output_format == OutputFormat.JSON:
            import json

            data = [{"type": el.category, "text": str(el)} for el in elements]
            content = json.dumps(data, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            parts = []
            for el in elements:
                tag = "h1" if el.category == "Title" else "p"
                parts.append(f"<{tag}>{el}</{tag}>")
            content = "<html><body>" + "\n".join(parts) + "</body></html>"
        elif output_format == OutputFormat.MARKDOWN:
            parts = []
            for el in elements:
                if el.category == "Title":
                    parts.append(f"# {el}")
                elif el.category == "Table":
                    parts.append(f"\n{el}\n")
                else:
                    parts.append(str(el))
            content = "\n\n".join(parts)
        else:
            content = "\n\n".join(str(el) for el in elements)

        metadata = {
            "strategy": self._strategy,
            "element_count": len(elements),
        }
        return content, metadata

"""PyMuPDF engine adapter — fast text extraction for digital PDFs.

Install: ``pip install docfold[pymupdf]``
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf"}


class PyMuPDFEngine(DocumentEngine):
    """Lightweight adapter for PyMuPDF (fitz) text extraction.

    Best for digital (non-scanned) PDFs where layout analysis is not critical.
    """

    @property
    def name(self) -> str:
        return "pymupdf"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    def is_available(self) -> bool:
        try:
            import fitz  # noqa: F401
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
        content, page_count = await loop.run_in_executor(
            None, self._extract, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=page_count,
            processing_time_ms=elapsed_ms,
            metadata={"method": "text_extraction"},
        )

    def _extract(self, file_path: str, output_format: OutputFormat) -> tuple[str, int]:
        import fitz

        doc = fitz.open(file_path)
        pages_text: list[str] = []

        for page in doc:
            pages_text.append(page.get_text())

        page_count = len(pages_text)
        full_text = "\n\n".join(pages_text)
        doc.close()

        if output_format == OutputFormat.JSON:
            import json
            content = json.dumps(
                {"pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages_text)]},
                ensure_ascii=False,
            )
        elif output_format == OutputFormat.HTML:
            html_parts = [f"<div class='page' data-page='{i+1}'><p>{t}</p></div>"
                          for i, t in enumerate(pages_text)]
            content = "<html><body>" + "\n".join(html_parts) + "</body></html>"
        else:
            content = full_text

        return content, page_count

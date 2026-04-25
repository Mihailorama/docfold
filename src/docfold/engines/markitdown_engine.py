"""MarkItDown engine adapter — Microsoft's open-source document-to-Markdown library.

MarkItDown is a pure-Python tool that converts a wide range of document formats
(Office files, PDFs, images, HTML, CSV/JSON/XML, ePub, audio, ZIP, ...) into
LLM-friendly Markdown.  See https://github.com/microsoft/markitdown.

Install: ``pip install docfold[markitdown]``
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from docfold.engines.base import (
    DocumentEngine,
    EngineCapabilities,
    EngineResult,
    OutputFormat,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    # Office
    "docx", "pptx", "xlsx", "xls",
    # PDFs
    "pdf",
    # Web / markup
    "html", "htm", "xml",
    # Tabular / structured data
    "csv", "tsv", "json",
    # Images (markitdown runs OCR/LLM captioning when configured)
    "png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp",
    # Audio (transcription)
    "mp3", "wav", "m4a",
    # eBooks / archives / misc
    "epub", "zip", "txt", "md",
}


class MarkItDownEngine(DocumentEngine):
    """Adapter for Microsoft's ``markitdown`` library.

    Markitdown converts documents to Markdown via its synchronous ``convert``
    method.  We dispatch the call through ``run_in_executor`` so it does not
    block the event loop.
    """

    def __init__(self, enable_plugins: bool = False) -> None:
        self._enable_plugins = enable_plugins
        self._converter: Any = None

    @property
    def name(self) -> str:
        return "markitdown"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        # Markitdown returns a Markdown string — no layout, bboxes, or
        # confidence scores.
        return EngineCapabilities()

    def is_available(self) -> bool:
        # markitdown's import chain pulls in pdfminer/cryptography, which can
        # raise non-ImportError exceptions (e.g. a broken PyO3 binding).
        # Treat any import failure as "unavailable" so a broken env cannot
        # knock out the whole router / benchmark harness.
        try:
            import markitdown  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def _get_converter(self) -> Any:
        if self._converter is None:
            from markitdown import MarkItDown
            self._converter = MarkItDown(enable_plugins=self._enable_plugins)
        return self._converter

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()

        try:
            converter = self._get_converter()
        except ImportError as exc:
            raise RuntimeError(
                "markitdown is not installed. Install with: pip install docfold[markitdown]"
            ) from exc
        except TypeError:
            # Older markitdown versions don't accept enable_plugins kwarg.
            from markitdown import MarkItDown
            self._converter = MarkItDown()
            converter = self._converter

        loop = asyncio.get_running_loop()
        convert_result = await loop.run_in_executor(None, converter.convert, file_path)

        markdown_text: str = getattr(convert_result, "text_content", "") or ""
        title = getattr(convert_result, "title", None)

        if output_format == OutputFormat.JSON:
            content = json.dumps({"markdown": markdown_text, "title": title},
                                 ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            # Minimal wrapper — markitdown doesn't render HTML itself.
            content = f"<pre class=\"markdown\">{markdown_text}</pre>"
        else:
            # MARKDOWN and TEXT both return the markdown string as-is.
            content = markdown_text

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata={
                "title": title,
                "enable_plugins": self._enable_plugins,
            },
        )

"""docling-serve remote engine adapter.

Calls a running docling-serve instance (CPU or GPU) via its REST API.

Requires ``requests`` (already a docfold dependency).

Environment variables:
    DOCLING_SERVE_URL   Base URL, e.g. ``https://docling-serve-xxx.a.run.app``
    DOCLING_SERVE_API_KEY   Optional API key (sent as ``X-Api-Key`` header)

See https://github.com/docling-project/docling-serve
"""

from __future__ import annotations

import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "pptx", "xlsx", "html",
    "png", "jpg", "jpeg", "tiff", "tif", "webp", "bmp",
}


class DoclingServeEngine(DocumentEngine):
    """Adapter for a remote docling-serve instance.

    Example::

        engine = DoclingServeEngine(base_url="https://my-instance.run.app")
        result = await engine.process("scan.pdf", output_format=OutputFormat.HTML)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        do_ocr: bool = True,
        timeout: int = 300,
    ) -> None:
        self._base_url = (
            base_url
            or os.getenv("DOCLING_SERVE_URL", "")
        ).rstrip("/")
        self._api_key = api_key or os.getenv("DOCLING_SERVE_API_KEY", "")
        self._do_ocr = do_ocr
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "docling_serve"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=False,
            images=True,
            table_structure=True,
            heading_detection=True,
            reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401
            return bool(self._base_url)
        except ImportError:
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        do_ocr = kwargs.get("do_ocr", self._do_ocr)
        timeout = kwargs.get("timeout", self._timeout)

        start = time.perf_counter()

        loop = asyncio.get_running_loop()
        content, pages, meta = await loop.run_in_executor(
            None, self._call_docling_serve, file_path, output_format, do_ocr, timeout
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=pages,
            processing_time_ms=elapsed_ms,
            metadata=meta,
        )

    def _call_docling_serve(
        self,
        file_path: str,
        output_format: OutputFormat,
        do_ocr: bool,
        timeout: int,
    ) -> tuple[str, int | None, dict]:
        import requests

        fmt_map = {
            OutputFormat.MARKDOWN: "md",
            OutputFormat.HTML: "html",
            OutputFormat.JSON: "json",
            OutputFormat.TEXT: "text",
        }
        ds_fmt = fmt_map.get(output_format, "md")

        content_field = {
            "md": "md_content",
            "html": "html_content",
            "json": "json_content",
            "text": "text_content",
        }[ds_fmt]

        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-Api-Key"] = self._api_key

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        with open(file_path, "rb") as f:
            files = [("files", (Path(file_path).name, f, mime_type))]
            data: dict[str, Any] = {
                "to_formats": [ds_fmt],
                "do_ocr": str(do_ocr).lower(),
            }

            resp = requests.post(
                f"{self._base_url}/v1/convert/file",
                files=files,
                data=data,
                headers=headers,
                timeout=timeout,
            )

        resp.raise_for_status()
        result = resp.json()

        doc = result.get("document", {})
        content = doc.get(content_field, "") or ""
        pages = doc.get("num_pages") or doc.get("page_count")

        meta = {
            "status": result.get("status"),
            "processing_time": result.get("processing_time"),
            "docling_serve_url": self._base_url,
        }

        return content, pages, meta

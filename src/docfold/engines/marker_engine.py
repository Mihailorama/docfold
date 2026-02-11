"""Marker API (Datalab) engine adapter.

Install: ``pip install docfold[marker]``

Requires a Datalab API key: https://www.datalab.to/
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls",
    "odt", "odp", "ods", "html", "epub",
    "png", "jpg", "jpeg", "webp", "gif", "tiff",
}

_API_BASE = "https://www.datalab.to/api/v1/marker"
_DEFAULT_POLL_INTERVAL = 2
_DEFAULT_MAX_POLLS = 300


class MarkerEngine(DocumentEngine):
    """Adapter for the Marker API (Datalab SaaS).

    See https://documentation.datalab.to/
    """

    def __init__(
        self,
        api_key: str | None = None,
        use_llm: bool = False,
        force_ocr: bool = False,
    ) -> None:
        self._api_key = api_key or os.getenv("MARKER_API_KEY") or os.getenv("DATALAB_API_KEY")
        self._use_llm = use_llm
        self._force_ocr = force_ocr

    @property
    def name(self) -> str:
        return "marker"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=True, images=True, table_structure=True,
            heading_detection=True,
        )

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401
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
        content, images, meta = await loop.run_in_executor(
            None, self._call_marker, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            images=images,
            pages=meta.get("page_count"),
            processing_time_ms=elapsed_ms,
            metadata=meta,
        )

    def _call_marker(
        self,
        file_path: str,
        output_format: OutputFormat,
    ) -> tuple[str, dict | None, dict]:
        import requests

        fmt_map = {
            OutputFormat.MARKDOWN: "markdown",
            OutputFormat.HTML: "html",
            OutputFormat.JSON: "json",
            OutputFormat.TEXT: "markdown",  # Marker doesn't have plain text; use markdown
        }
        marker_fmt = fmt_map[output_format]

        headers = {"X-Api-Key": self._api_key}

        with open(file_path, "rb") as f:
            form_data = {
                "file": (Path(file_path).name, f, "application/octet-stream"),
                "output_format": (None, marker_fmt),
                "use_llm": (None, str(self._use_llm)),
                "force_ocr": (None, str(self._force_ocr)),
                "paginate": (None, "False"),
                "strip_existing_ocr": (None, "False"),
                "disable_image_extraction": (None, "False"),
            }
            resp = requests.post(_API_BASE, files=form_data, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        check_url = data["request_check_url"]

        for _ in range(_DEFAULT_MAX_POLLS):
            time.sleep(_DEFAULT_POLL_INTERVAL)
            resp = requests.get(check_url, headers=headers, timeout=30)
            result = resp.json()

            if result.get("status") == "complete":
                content = result.get(marker_fmt, "")
                images = result.get("images")
                meta = {
                    "page_count": result.get("page_count"),
                    "marker_output_format": marker_fmt,
                }
                return content, images, meta

            if result.get("status") == "failed":
                raise RuntimeError(f"Marker API failed: {result.get('error')}")

        raise TimeoutError("Marker API did not complete within the polling window.")

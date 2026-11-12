"""Marker on your own GPU endpoint (Modal, RunPod, any HTTP host).

The endpoint takes ``{"file_base64", "filename", "output_format"}`` as JSON and
returns ``{"content", "images", "pages", "processing_time_ms"}``. A minimal
Modal server is in ``docs/examples/modal_marker_app.py``. No extra install.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

_EXTENSIONS = {
    "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "odt", "odp", "ods", "html", "epub",
    "png", "jpg", "jpeg", "webp", "gif", "tiff",
}
_FORMAT = {OutputFormat.HTML: "html", OutputFormat.JSON: "html"}


class RemoteMarkerEngine(DocumentEngine):
    """Marker over HTTP. URL: argument, ``DOCFOLD_REMOTE_MARKER_URL`` or ``MODAL_MARKER_URL``."""

    def __init__(
        self,
        url: str | None = None,
        name: str = "modal_marker",
        timeout: float = 120,
        retries: int = 1,
    ) -> None:
        self._url = url
        self._name = name
        self._timeout = timeout
        self._retries = retries

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_extensions(self) -> set[str]:
        return _EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(images=True, table_structure=True, heading_detection=True)

    def _endpoint(self) -> str:
        return (
            self._url or os.getenv("DOCFOLD_REMOTE_MARKER_URL") or os.getenv("MODAL_MARKER_URL")
            or ""
        )

    def is_available(self) -> bool:
        return bool(self._endpoint())

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()
        payload = json.dumps({
            "file_base64": base64.b64encode(Path(file_path).read_bytes()).decode("ascii"),
            "filename": Path(file_path).name,
            "output_format": _FORMAT.get(output_format, "markdown"),
        }).encode()
        loop = asyncio.get_running_loop()
        last: Exception | None = None
        for _ in range(self._retries + 1):
            try:
                data = await loop.run_in_executor(None, self._post, payload)
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                last = exc
        else:
            raise RuntimeError(f"{self._name}: request failed: {last}") from last
        return EngineResult(
            content=data.get("content", ""),
            format=output_format,
            engine_name=self._name,
            images=data.get("images") or None,
            pages=data.get("pages"),
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={
                "gpu_processing_time_ms": data.get("processing_time_ms", 0),
                "wall_time_ms": int((time.perf_counter() - start) * 1000),
            },
        )

    def _post(self, payload: bytes) -> dict[str, Any]:
        req = urllib.request.Request(
            self._endpoint(), payload, {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            result: dict[str, Any] = json.loads(resp.read())
            return result

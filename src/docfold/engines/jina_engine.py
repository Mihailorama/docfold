"""Jina Reader engine: PDFs and images to Markdown through ``r.jina.ai``.

API key: constructor, ``JINA_API_KEY`` or ``JINAAI_API_KEY``. The file is sent
to Jina's servers. No extra install.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

_FORMAT = {OutputFormat.HTML: "html", OutputFormat.TEXT: "text"}


class JinaEngine(DocumentEngine):
    """PDF -> ``POST https://r.jina.ai/`` with ``{"pdf": <base64>}`` -> content."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://r.jina.ai/",
        timeout: float = 180,
    ) -> None:
        self._api_key = api_key or os.getenv("JINA_API_KEY") or os.getenv("JINAAI_API_KEY")
        self._base_url = base_url
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "jina"

    @property
    def supported_extensions(self) -> set[str]:
        return {"pdf"}

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()
        body = json.dumps({
            "pdf": base64.b64encode(Path(file_path).read_bytes()).decode("ascii"),
        }).encode()
        headers = {
            "Authorization": f"Bearer {self._api_key or ''}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Return-Format": _FORMAT.get(output_format, "markdown"),
        }
        data = await asyncio.get_running_loop().run_in_executor(None, self._post, body, headers)
        doc = data.get("data") or {}
        content = doc.get("content") or ""
        if output_format == OutputFormat.JSON:
            content = json.dumps({"title": doc.get("title"), "content": content},
                                 ensure_ascii=False)
        usage = doc.get("usage") or {}
        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={"title": doc.get("title"), "tokens": usage.get("tokens")},
        )

    def _post(self, body: bytes, headers: dict[str, str]) -> dict[str, Any]:
        req = urllib.request.Request(self._base_url, body, headers)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            result: dict[str, Any] = json.loads(resp.read())
            return result

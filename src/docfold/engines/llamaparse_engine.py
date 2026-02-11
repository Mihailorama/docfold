"""LlamaParse engine adapter — LLM-powered document parsing by LlamaIndex.

Install: ``pip install docfold[llamaparse]``

Requires an API key: https://cloud.llamaindex.ai/
Set ``LLAMA_CLOUD_API_KEY`` environment variable.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls",
    "html", "htm", "png", "jpg", "jpeg", "csv", "epub",
}


class LlamaParseEngine(DocumentEngine):
    """Adapter for LlamaParse (LlamaIndex Cloud).

    LLM-powered parsing with excellent table and layout understanding.
    Free tier: 1000 pages/day.

    See https://docs.llamaindex.ai/en/stable/llama_cloud/llama_parse/
    """

    def __init__(self, api_key: str | None = None, result_type: str = "markdown") -> None:
        self._api_key = api_key or os.getenv("LLAMA_CLOUD_API_KEY")
        self._result_type = result_type

    @property
    def name(self) -> str:
        return "llamaparse"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(table_structure=True, heading_detection=True)

    def is_available(self) -> bool:
        try:
            import llama_parse  # noqa: F401

            return bool(self._api_key)
        except ImportError:
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()

        content, metadata = await self._parse(file_path, output_format)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata=metadata,
        )

    async def _parse(
        self, file_path: str, output_format: OutputFormat
    ) -> tuple[str, dict]:
        from llama_parse import LlamaParse

        fmt_map = {
            OutputFormat.MARKDOWN: "markdown",
            OutputFormat.HTML: "html",
            OutputFormat.JSON: "markdown",
            OutputFormat.TEXT: "text",
        }
        result_type = fmt_map[output_format]

        parser = LlamaParse(api_key=self._api_key, result_type=result_type)
        documents = await parser.aload_data(file_path)

        content = "\n\n".join(doc.text for doc in documents)

        if output_format == OutputFormat.JSON:
            import json

            data = [{"page": i + 1, "text": doc.text} for i, doc in enumerate(documents)]
            content = json.dumps(data, ensure_ascii=False)

        metadata = {
            "result_type": result_type,
            "document_count": len(documents),
        }
        return content, metadata

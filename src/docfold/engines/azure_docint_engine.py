"""Azure Document Intelligence engine adapter — cloud document analysis.

Install: ``pip install docfold[azure-docint]``

Requires Azure credentials:
- ``AZURE_DOCINT_ENDPOINT`` — the endpoint URL
- ``AZURE_DOCINT_KEY`` — the API key
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp",
    "docx", "xlsx", "pptx", "html",
}


class AzureDocIntEngine(DocumentEngine):
    """Adapter for Azure Document Intelligence (formerly Form Recognizer).

    Uses the ``prebuilt-layout`` model by default for general-purpose
    document analysis with table, heading, and reading order extraction.

    Supports DOCX, XLSX, PPTX natively in addition to PDF and images.

    See https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/
    """

    def __init__(
        self,
        endpoint: str | None = None,
        key: str | None = None,
        model_id: str = "prebuilt-layout",
    ) -> None:
        self._endpoint = endpoint or os.getenv("AZURE_DOCINT_ENDPOINT")
        self._key = key or os.getenv("AZURE_DOCINT_KEY")
        self._model_id = model_id

    @property
    def name(self) -> str:
        return "azure_docint"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=True, confidence=True, table_structure=True,
            heading_detection=True, reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import azure.ai.documentintelligence  # noqa: F401

            return bool(self._endpoint and self._key)
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
        content, metadata, boxes, conf, tables = await loop.run_in_executor(
            None, self._analyze, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            processing_time_ms=elapsed_ms,
            metadata=metadata,
            bounding_boxes=boxes,
            confidence=conf,
            tables=tables,
        )

    def _analyze(
        self,
        file_path: str,
        output_format: OutputFormat,
    ) -> tuple[str, dict, list[dict], float | None, list[dict] | None]:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        client = DocumentIntelligenceClient(
            endpoint=self._endpoint,
            credential=AzureKeyCredential(self._key),
        )

        with open(file_path, "rb") as f:
            poller = client.begin_analyze_document(
                model_id=self._model_id,
                analyze_request=f,
                content_type="application/octet-stream",
                output_content_format="markdown",
            )

        result = poller.result()

        # Primary content — Azure returns markdown by default
        full_text = result.content or ""

        # Extract bounding boxes and confidence from paragraphs
        bounding_boxes: list[dict[str, Any]] = []
        confidences: list[float] = []

        for paragraph in result.paragraphs or []:
            conf = paragraph.confidence
            if conf is not None:
                confidences.append(conf)

            polygon = None
            if paragraph.bounding_regions:
                region = paragraph.bounding_regions[0]
                polygon = region.polygon
                page_num = region.page_number
            else:
                page_num = 1

            bounding_boxes.append({
                "type": "paragraph",
                "role": paragraph.role,
                "text": paragraph.content,
                "polygon": polygon,
                "page": page_num,
                "confidence": conf,
            })

        avg_conf = sum(confidences) / len(confidences) if confidences else None

        # Extract tables
        tables: list[dict[str, Any]] = []
        for table in result.tables or []:
            table_data = self._extract_table(table)
            if table_data:
                tables.append(table_data)

        # Format output
        if output_format == OutputFormat.JSON:
            import json
            data = {"text": full_text, "page_count": len(result.pages or [])}
            content = json.dumps(data, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            content = f"<html><body><pre>{full_text}</pre></body></html>"
        else:
            content = full_text

        metadata = {
            "page_count": len(result.pages or []),
            "model_id": self._model_id,
            "paragraph_count": len(result.paragraphs or []),
            "table_count": len(tables),
        }

        return content, metadata, bounding_boxes, avg_conf, tables or None

    def _extract_table(self, table: Any) -> dict[str, Any] | None:
        """Extract table structure from Azure table object."""
        if not table.cells:
            return None

        rows: dict[int, dict[int, str]] = {}
        for cell in table.cells:
            row_idx = cell.row_index
            col_idx = cell.column_index
            rows.setdefault(row_idx, {})[col_idx] = cell.content or ""

        return {
            "row_count": table.row_count,
            "column_count": table.column_count,
            "rows": [
                {f"col_{c}": rows[r].get(c, "") for c in sorted(rows[r])}
                for r in sorted(rows)
            ],
        }

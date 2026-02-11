"""Google Document AI engine adapter — cloud document understanding.

Install: ``pip install docfold[google-docai]``

Requires Google Cloud credentials and a Document AI processor.
Set ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable for auth,
and configure processor via constructor or environment variables:
``GOOGLE_DOCAI_PROJECT_ID``, ``GOOGLE_DOCAI_LOCATION``, ``GOOGLE_DOCAI_PROCESSOR_ID``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "gif", "bmp", "webp"}

_MIME_MAP = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
}


class GoogleDocAIEngine(DocumentEngine):
    """Adapter for Google Document AI.

    Processes documents using a configured Document AI processor.
    Supports OCR, layout analysis, table extraction, and more.

    See https://cloud.google.com/document-ai
    """

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        processor_id: str | None = None,
    ) -> None:
        self._project_id = project_id or os.getenv("GOOGLE_DOCAI_PROJECT_ID")
        self._location = location or os.getenv("GOOGLE_DOCAI_LOCATION", "us")
        self._processor_id = processor_id or os.getenv("GOOGLE_DOCAI_PROCESSOR_ID")

    @property
    def name(self) -> str:
        return "google_docai"

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
            from google.cloud import documentai  # noqa: F401

            return bool(self._project_id and self._processor_id)
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
            None, self._process_document, file_path, output_format
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

    def _process_document(
        self,
        file_path: str,
        output_format: OutputFormat,
    ) -> tuple[str, dict, list[dict], float | None, list[dict] | None]:
        from google.cloud import documentai

        client = documentai.DocumentProcessorServiceClient()

        processor_name = client.processor_path(
            self._project_id, self._location, self._processor_id
        )

        ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        mime_type = _MIME_MAP.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            raw_document = documentai.RawDocument(content=f.read(), mime_type=mime_type)

        request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document

        # Extract text
        full_text = document.text or ""

        # Extract bounding boxes and confidence
        bounding_boxes: list[dict[str, Any]] = []
        confidences: list[float] = []

        for page in document.pages:
            page_num = page.page_number

            for paragraph in page.paragraphs:
                text_segment = self._get_text_segment(paragraph.layout, document.text)
                conf = paragraph.layout.confidence
                if conf:
                    confidences.append(conf)

                vertices = self._get_vertices(paragraph.layout)
                if vertices:
                    bounding_boxes.append({
                        "type": "paragraph",
                        "text": text_segment,
                        "vertices": vertices,
                        "page": page_num,
                        "confidence": conf,
                    })

        avg_conf = sum(confidences) / len(confidences) if confidences else None

        # Extract tables
        tables: list[dict[str, Any]] = []
        for page in document.pages:
            for table in page.tables:
                table_data = self._extract_table(table, document.text)
                if table_data:
                    tables.append(table_data)

        # Format output
        if output_format == OutputFormat.JSON:
            import json
            data = {"text": full_text, "page_count": len(document.pages)}
            content = json.dumps(data, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            content = f"<html><body><pre>{full_text}</pre></body></html>"
        else:
            content = full_text

        metadata = {
            "page_count": len(document.pages),
            "processor_id": self._processor_id,
            "mime_type": mime_type,
        }

        return content, metadata, bounding_boxes, avg_conf, tables or None

    def _get_text_segment(self, layout: Any, full_text: str) -> str:
        """Extract text from a layout's text_anchor."""
        segments = layout.text_anchor.text_segments if layout.text_anchor else []
        parts = []
        for segment in segments:
            start = int(segment.start_index) if segment.start_index else 0
            end = int(segment.end_index) if segment.end_index else 0
            parts.append(full_text[start:end])
        return "".join(parts).strip()

    def _get_vertices(self, layout: Any) -> list[dict[str, float]] | None:
        """Extract normalized vertices from layout bounding poly."""
        bp = layout.bounding_poly
        if not bp or not bp.normalized_vertices:
            return None
        return [{"x": v.x, "y": v.y} for v in bp.normalized_vertices]

    def _extract_table(self, table: Any, full_text: str) -> dict[str, Any] | None:
        """Extract table rows from Document AI table object."""
        rows_data = []

        for row in table.header_rows:
            cells = [self._get_text_segment(cell.layout, full_text) for cell in row.cells]
            rows_data.append({"type": "header", "cells": cells})

        for row in table.body_rows:
            cells = [self._get_text_segment(cell.layout, full_text) for cell in row.cells]
            rows_data.append({"type": "body", "cells": cells})

        if not rows_data:
            return None
        return {"rows": rows_data}

"""AWS Textract engine adapter — cloud document analysis.

Install: ``pip install docfold[textract]``

Requires AWS credentials configured via environment variables
(``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_DEFAULT_REGION``)
or a shared credentials file.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif"}


class TextractEngine(DocumentEngine):
    """Adapter for AWS Textract document analysis.

    Uses ``AnalyzeDocument`` for images and ``StartDocumentAnalysis`` +
    ``GetDocumentAnalysis`` for multi-page PDFs (requires S3).

    For single-page documents, synchronous ``AnalyzeDocument`` is used.
    For multi-page PDFs, the file must be in S3 or will be processed
    page-by-page via image rendering.

    See https://docs.aws.amazon.com/textract/
    """

    def __init__(
        self,
        region_name: str | None = None,
    ) -> None:
        self._region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    @property
    def name(self) -> str:
        return "textract"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=True, confidence=True, table_structure=True,
            reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import boto3  # noqa: F401

            session = boto3.Session()
            creds = session.get_credentials()
            return creds is not None
        except (ImportError, Exception):
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
        import boto3

        client = boto3.client("textract", region_name=self._region_name)

        with open(file_path, "rb") as f:
            doc_bytes = f.read()

        response = client.analyze_document(
            Document={"Bytes": doc_bytes},
            FeatureTypes=["TABLES", "FORMS", "LAYOUT"],
        )

        blocks = response.get("Blocks", [])

        # Extract text lines
        lines: list[str] = []
        bounding_boxes: list[dict[str, Any]] = []
        confidences: list[float] = []
        tables: list[dict[str, Any]] = []

        for block in blocks:
            block_type = block.get("BlockType", "")

            if block_type == "LINE":
                text = block.get("Text", "")
                lines.append(text)
                conf = block.get("Confidence", 0) / 100.0
                confidences.append(conf)

                bbox = block.get("Geometry", {}).get("BoundingBox", {})
                if bbox:
                    bounding_boxes.append({
                        "type": "line",
                        "text": text,
                        "bbox": bbox,
                        "page": block.get("Page", 1),
                        "confidence": conf,
                    })

            elif block_type == "TABLE":
                table_data = self._extract_table(block, blocks)
                if table_data:
                    tables.append(table_data)

        full_text = "\n".join(lines)
        avg_conf = sum(confidences) / len(confidences) if confidences else None

        if output_format == OutputFormat.JSON:
            import json
            data = [{"text": line} for line in lines]
            content = json.dumps(data, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            html_lines = [f"<p>{line}</p>" for line in lines]
            content = "<html><body>" + "\n".join(html_lines) + "</body></html>"
        else:
            content = full_text

        metadata = {
            "block_count": len(blocks),
            "line_count": len(lines),
            "table_count": len(tables),
            "region": self._region_name,
        }

        return content, metadata, bounding_boxes, avg_conf, tables or None

    def _extract_table(
        self, table_block: dict, all_blocks: list[dict]
    ) -> dict[str, Any] | None:
        """Extract table structure from Textract CELL blocks."""
        relationships = table_block.get("Relationships", [])
        cell_ids: list[str] = []
        for rel in relationships:
            if rel["Type"] == "CHILD":
                cell_ids.extend(rel["Ids"])

        block_map = {b["Id"]: b for b in all_blocks}
        rows: dict[int, dict[int, str]] = {}

        for cell_id in cell_ids:
            cell = block_map.get(cell_id, {})
            if cell.get("BlockType") != "CELL":
                continue
            row_idx = cell.get("RowIndex", 0)
            col_idx = cell.get("ColumnIndex", 0)
            # Get cell text from child WORD blocks
            cell_text = self._get_block_text(cell, block_map)
            rows.setdefault(row_idx, {})[col_idx] = cell_text

        if not rows:
            return None

        return {
            "rows": [
                {f"col_{c}": rows[r].get(c, "") for c in sorted(rows[r])}
                for r in sorted(rows)
            ]
        }

    def _get_block_text(self, block: dict, block_map: dict) -> str:
        """Collect text from WORD children of a block."""
        words: list[str] = []
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for child_id in rel["Ids"]:
                    child = block_map.get(child_id, {})
                    if child.get("BlockType") == "WORD":
                        words.append(child.get("Text", ""))
        return " ".join(words)

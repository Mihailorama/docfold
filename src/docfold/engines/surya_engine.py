"""Surya engine adapter — high-performance OCR and layout analysis.

Install: ``pip install docfold[surya]``

Surya provides text detection, recognition, layout analysis, and table
structure extraction with support for 90+ languages.

No API key needed; runs entirely locally.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp", "tiff", "bmp", "gif"}


class SuryaEngine(DocumentEngine):
    """Adapter for Surya OCR + layout analysis.

    Surya provides bounding boxes, confidence scores, layout labels, table
    structure, and reading-order detection for PDFs and images in 90+ languages.

    See https://github.com/VikParuchuri/surya
    """

    def __init__(
        self,
        langs: list[str] | None = None,
    ) -> None:
        self._langs = langs or ["en"]

    @property
    def name(self) -> str:
        return "surya"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=True,
            confidence=True,
            images=True,
            table_structure=True,
            heading_detection=True,
            reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import surya  # noqa: F401
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
        content, page_count, metadata = await loop.run_in_executor(
            None, self._do_process, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=page_count,
            processing_time_ms=elapsed_ms,
            metadata=metadata,
        )

    def _load_images(self, file_path: str) -> list[Any]:
        """Load images from a PDF or image file."""
        from PIL import Image

        path = Path(file_path)
        ext = path.suffix.lstrip(".").lower()

        if ext == "pdf":
            from surya.input.processing import get_page_images, open_pdf

            doc = open_pdf(file_path)
            page_count = len(doc)
            images = get_page_images(doc, list(range(page_count)))
            doc.close()
            return images
        else:
            return [Image.open(file_path)]

    def _do_process(
        self, file_path: str, output_format: OutputFormat
    ) -> tuple[str, int, dict]:
        # Surya v0.17+ predictor-based API
        from surya.detection import DetectionPredictor
        from surya.foundation import FoundationPredictor
        from surya.recognition import RecognitionPredictor

        images = self._load_images(file_path)
        page_count = len(images)

        det_predictor = DetectionPredictor()
        foundation = FoundationPredictor()
        rec_predictor = RecognitionPredictor(foundation)

        # Run OCR (detection + recognition)
        predictions = rec_predictor(
            images,
            det_predictor=det_predictor,
        )

        # Build structured pages
        pages_data: list[dict] = []
        for page_idx, ocr_result in enumerate(predictions):
            lines = []
            for line in ocr_result.text_lines:
                lines.append({
                    "text": line.text,
                    "polygon": line.polygon,
                    "confidence": line.confidence,
                })

            pages_data.append({
                "page": page_idx + 1,
                "lines": lines,
            })

        # Format output
        content = self._format_output(pages_data, output_format)
        metadata = {"langs": self._langs}

        return content, page_count, metadata

    def _format_output(
        self, pages_data: list[dict], output_format: OutputFormat
    ) -> str:
        if output_format == OutputFormat.JSON:
            import json
            return json.dumps({"pages": pages_data}, ensure_ascii=False)

        if output_format == OutputFormat.HTML:
            html_parts = []
            for page in pages_data:
                lines_html = "".join(
                    f"<p>{line['text']}</p>" for line in page["lines"]
                )
                html_parts.append(
                    f"<div class='page' data-page='{page['page']}'>{lines_html}</div>"
                )
            return "<html><body>" + "\n".join(html_parts) + "</body></html>"

        # MARKDOWN / TEXT
        md_parts = []
        for page in pages_data:
            page_lines: list[str] = []
            for line in page["lines"]:
                page_lines.append(line["text"])
            md_parts.append("\n".join(page_lines))
        return "\n\n".join(md_parts)

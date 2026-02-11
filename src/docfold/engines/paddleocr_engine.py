"""PaddleOCR engine adapter — multilingual OCR for scanned documents.

Install: ``pip install docfold[paddleocr]``
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp", "pdf"}


class PaddleOCREngine(DocumentEngine):
    """OCR-based extraction using PaddleOCR.

    Supports 80+ languages. For PDFs, pages are rendered to images first.
    """

    def __init__(self, lang: str = "en") -> None:
        self._lang = lang

    @property
    def name(self) -> str:
        return "paddleocr"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(confidence=True)

    def is_available(self) -> bool:
        try:
            import paddleocr  # noqa: F401

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
        text, confidence = await loop.run_in_executor(None, self._run_ocr, file_path)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=text,
            format=OutputFormat.TEXT,
            engine_name=self.name,
            confidence=confidence,
            processing_time_ms=elapsed_ms,
            metadata={"lang": self._lang},
        )

    def _run_ocr(self, file_path: str) -> tuple[str, float | None]:
        ext = Path(file_path).suffix.lstrip(".").lower()

        if ext == "pdf":
            return self._ocr_pdf(file_path)
        return self._ocr_image(file_path)

    def _ocr_image(self, image_path: str) -> tuple[str, float | None]:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(lang=self._lang, show_log=False)
        result = ocr.ocr(image_path, cls=True)

        lines: list[str] = []
        confidences: list[float] = []

        if result and result[0]:
            for line_info in result[0]:
                text = line_info[1][0]
                conf = line_info[1][1]
                lines.append(text)
                confidences.append(conf)

        full_text = "\n".join(lines)
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        return full_text, avg_conf

    def _ocr_pdf(self, pdf_path: str) -> tuple[str, float | None]:
        """Convert PDF pages to images then OCR each page."""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError("pdf2image is required for OCR on PDFs: pip install pdf2image")

        images = convert_from_path(pdf_path)
        texts: list[str] = []
        confidences: list[float] = []

        for img in images:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                img.save(tmp_path)
                text, conf = self._ocr_image(tmp_path)
                texts.append(text)
                if conf is not None:
                    confidences.append(conf)
            finally:
                os.unlink(tmp_path)

        full_text = "\n\n".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        return full_text, avg_conf

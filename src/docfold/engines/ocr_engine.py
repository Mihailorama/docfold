"""OCR engine adapter — PaddleOCR with Tesseract fallback.

Install: ``pip install docfold[ocr]``
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp", "pdf"}


class OCREngine(DocumentEngine):
    """OCR-based extraction using PaddleOCR (primary) and Tesseract (fallback).

    For PDFs, pages are first rendered to images, then OCR is applied.
    """

    def __init__(self, lang: str = "en", use_paddle: bool = True) -> None:
        self._lang = lang
        self._use_paddle = use_paddle

    @property
    def name(self) -> str:
        return "ocr"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    def is_available(self) -> bool:
        if self._use_paddle:
            try:
                import paddleocr  # noqa: F401
                return True
            except ImportError:
                pass
        try:
            import pytesseract  # noqa: F401
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
            metadata={"lang": self._lang, "paddle": self._use_paddle},
        )

    def _run_ocr(self, file_path: str) -> tuple[str, float | None]:
        ext = Path(file_path).suffix.lstrip(".").lower()

        if ext == "pdf":
            return self._ocr_pdf(file_path)
        return self._ocr_image(file_path)

    def _ocr_image(self, image_path: str) -> tuple[str, float | None]:
        if self._use_paddle:
            try:
                return self._paddle_ocr(image_path)
            except Exception:
                logger.warning("PaddleOCR failed, falling back to Tesseract", exc_info=True)

        return self._tesseract_ocr(image_path)

    def _ocr_pdf(self, pdf_path: str) -> tuple[str, float | None]:
        """Convert PDF pages to images then OCR each page."""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError("pdf2image is required for OCR on PDFs: pip install pdf2image")

        images = convert_from_path(pdf_path)
        texts: list[str] = []
        confidences: list[float] = []

        import os
        import tempfile

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

    def _paddle_ocr(self, image_path: str) -> tuple[str, float | None]:
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

    def _tesseract_ocr(self, image_path: str) -> tuple[str, float | None]:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=self._lang)
        return text.strip(), None

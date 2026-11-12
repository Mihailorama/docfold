"""Lightweight file pre-analysis for routing decisions.

This is a **standalone utility** — NOT coupled to EngineRouter.
Consumers can use it to decide which engine to request via ``engine_hint``.

Example::

    from docfold.utils import pre_analyze

    analysis = await pre_analyze("invoice.pdf")
    if analysis.category == "pdf_text":
        result = await router.process("invoice.pdf", engine_hint="pymupdf")
    elif analysis.category == "pdf_scanned":
        result = await router.process("invoice.pdf", engine_hint="tesseract")
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Extension-based MIME type lookup (subset for common document types)
_MIME_MAP: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "gif": "image/gif",
    "html": "text/html",
    "htm": "text/html",
    "csv": "text/csv",
    "epub": "application/epub+zip",
}

# Extension → category for non-PDF types
_CATEGORY_MAP: dict[str, str] = {
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "tiff": "image",
    "tif": "image",
    "bmp": "image",
    "webp": "image",
    "gif": "image",
    "docx": "office",
    "doc": "office",
    "pptx": "office",
    "ppt": "office",
    "xlsx": "office",
    "xls": "office",
    "odt": "office",
    "rtf": "office",
    "csv": "office",
    "html": "html",
    "htm": "html",
    "epub": "ebook",
}

# Minimum extracted text length (chars) to consider a PDF as text-based
_TEXT_LAYER_THRESHOLD = 100

# Max pages to sample for text layer detection
_SAMPLE_PAGES = 2


@dataclass
class FileAnalysis:
    """Result of file pre-analysis."""

    mime_type: str
    """e.g. ``"application/pdf"``"""

    extension: str
    """e.g. ``"pdf"``"""

    file_size_bytes: int

    category: str
    """e.g. ``"pdf_text"``, ``"pdf_scanned"``, ``"image"``, ``"office"``, ``"html"``"""

    page_count: int | None = None
    """For PDFs only."""

    has_text_layer: bool | None = None
    """For PDFs: ``True`` = text-based, ``False`` = scanned."""

    detected_language: str | None = None
    """e.g. ``"en"``, ``"ru"`` (only if langdetect is available)."""


async def pre_analyze(file_path: str) -> FileAnalysis:
    """Classify a file for routing decisions (~50ms target).

    For PDFs:
    - Open with pymupdf, try extracting text from first 2 pages.
    - If text length > 100 chars → ``category = "pdf_text"``
    - If text length ≤ 100 → ``category = "pdf_scanned"``
    - Count pages.

    For images: ``category = "image"``
    For office docs: ``category = "office"``
    For HTML: ``category = "html"``
    For unknown: ``category = "unknown"``
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _analyze_sync, file_path)


def _analyze_sync(file_path: str) -> FileAnalysis:
    """Synchronous implementation of file analysis."""
    path = Path(file_path)
    ext = path.suffix.lstrip(".").lower()
    mime = _MIME_MAP.get(ext, "application/octet-stream")
    file_size = os.path.getsize(file_path)

    if ext == "pdf":
        return _analyze_pdf(file_path, ext, mime, file_size)

    category = _CATEGORY_MAP.get(ext, "unknown")
    return FileAnalysis(
        mime_type=mime,
        extension=ext,
        file_size_bytes=file_size,
        category=category,
    )


def _analyze_pdf(file_path: str, ext: str, mime: str, file_size: int) -> FileAnalysis:
    """Analyze a PDF: count pages and detect text layer."""
    page_count: int | None = None
    has_text_layer: bool | None = None
    category = "pdf_text"
    detected_language: str | None = None

    try:
        import pymupdf

        doc = pymupdf.open(file_path)
        page_count = len(doc)

        # Sample first N pages for text extraction
        sample_text_parts: list[str] = []
        pages_to_check = min(_SAMPLE_PAGES, page_count)
        for i in range(pages_to_check):
            page = doc[i]
            sample_text_parts.append(page.get_text())
        doc.close()

        sample_text = "".join(sample_text_parts).strip()
        has_text_layer = len(sample_text) > _TEXT_LAYER_THRESHOLD
        category = "pdf_text" if has_text_layer else "pdf_scanned"

        # Optional language detection
        if has_text_layer and sample_text:
            detected_language = _detect_language(sample_text)

    except ImportError:
        logger.debug("pymupdf not installed — skipping PDF text layer detection")
    except Exception:
        logger.warning("Failed to analyze PDF %s", file_path, exc_info=True)

    return FileAnalysis(
        mime_type=mime,
        extension=ext,
        file_size_bytes=file_size,
        category=category,
        page_count=page_count,
        has_text_layer=has_text_layer,
        detected_language=detected_language,
    )


def _detect_language(text: str) -> str | None:
    """Detect language using langdetect if available, otherwise return None."""
    try:
        from langdetect import detect

        # Use first 1000 chars for speed
        return detect(text[:1000])
    except ImportError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-page classification and PDF metadata (DOCFOLD-22)
# ---------------------------------------------------------------------------


def classify_pages(file_path: str) -> list[str]:
    """Classify each PDF page as ``text``, ``image``, ``mixed`` or ``empty``.

    Based on text and image block areas (PyMuPDF ``get_text("blocks")``), so a
    scanned annex inside a digital PDF shows up page by page.
    """
    import pymupdf

    kinds: list[str] = []
    with pymupdf.open(file_path) as doc:
        for page in doc:
            text_area = image_area = 0.0
            flags = pymupdf.TEXTFLAGS_BLOCKS | pymupdf.TEXT_PRESERVE_IMAGES
            for block in page.get_text("blocks", flags=flags):
                area = abs(pymupdf.Rect(block[:4]))
                if block[6] == 1:
                    image_area += area
                elif str(block[4]).strip():
                    text_area += area
            if text_area and image_area:
                kinds.append("mixed")
            elif text_area:
                kinds.append("text")
            elif image_area:
                kinds.append("image")
            else:
                kinds.append("empty")
    return kinds


def pdf_metadata(file_path: str, sample_pages: int = 5) -> dict[str, Any]:
    """Document facts for a PDF: encryption, info fields, content seen on the first pages.

    ``is_scanned`` is ``True`` when the sampled pages have images and no text,
    ``False`` for text without images, ``None`` for mixed or empty content.
    Encrypted files report only ``page_count`` / ``encrypted`` / ``needs_password``.
    """
    import pymupdf

    with pymupdf.open(file_path) as doc:
        info = doc.metadata or {}
        meta: dict[str, Any] = {
            "page_count": doc.page_count,
            "encrypted": bool(doc.is_encrypted or doc.needs_pass),
            "needs_password": bool(doc.needs_pass),
            "title": info.get("title") or None,
            "author": info.get("author") or None,
            "creator": info.get("creator") or None,
            "producer": info.get("producer") or None,
            "creation_date": info.get("creationDate") or None,
        }
        types: set[str] = set()
        if not doc.needs_pass:
            for page in list(doc)[:sample_pages]:
                if page.get_text().strip():
                    types.add("text")
                if page.get_images():
                    types.add("images")
                if page.find_tables().tables:
                    types.add("tables")
                if next(page.widgets(), None) is not None:
                    types.add("forms")
                if next(page.annots(), None) is not None:
                    types.add("annotations")
    meta["content_types"] = sorted(types)
    meta["has_forms"] = "forms" in types
    meta["has_annotations"] = "annotations" in types
    has_text, has_images = "text" in types, "images" in types
    meta["is_scanned"] = True if has_images and not has_text else (
        False if has_text and not has_images else None
    )
    return meta

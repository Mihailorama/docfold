"""Render document pages to images, one page at a time.

Install: ``pip install docfold[render]`` (PyMuPDF + Pillow). Office files
need LibreOffice (``soffice``) on PATH.

Example::

    import base64
    from docfold.render import render_pages

    for page, data in render_pages("report.pdf", "1-3", image_format="jpeg"):
        b64 = base64.b64encode(data).decode()
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path

from docfold.split import _page_ranges

OFFICE_EXTENSIONS = {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "odt", "ods", "odp", "rtf"}
_FORMATS = {"png", "jpeg", "jpg", "webp"}


def render_pages(
    file_path: str,
    pages: str | Iterable[int] | None = None,
    *,
    dpi: int = 150,
    image_format: str = "png",
    quality: int = 85,
    office_timeout: int = 120,
) -> Iterator[tuple[int, bytes]]:
    """Yield ``(page_number, image_bytes)`` for each requested page.

    Args:
        file_path: PDF, image, or office file (converted with LibreOffice).
        pages: ``"1-3,7"`` or 1-based page numbers; ``None`` renders all.
            Pages outside the document are skipped.
        dpi: Render resolution.
        image_format: ``png``, ``jpeg`` or ``webp`` (webp needs Pillow).
        quality: jpeg/webp quality, 1-100.
        office_timeout: Seconds allowed for the LibreOffice conversion.

    Pages are rendered and encoded lazily, so a long document never sits in
    memory as a whole. Encoding costs about as much as rendering for PNG;
    jpeg with Pillow installed encodes about 5x faster than PNG, webp gives
    the smallest files but encodes slowest.
    """
    fmt = image_format.lower()
    if fmt not in _FORMATS:
        raise ValueError(f"image_format must be one of {sorted(_FORMATS)}, got {image_format!r}")
    import pymupdf

    has_pil = importlib.util.find_spec("PIL") is not None
    ext = Path(file_path).suffix.lstrip(".").lower()
    with tempfile.TemporaryDirectory(prefix="docfold_render_") as tmp:
        src = file_path
        if ext in OFFICE_EXTENSIONS:
            src = _office_to_pdf(file_path, tmp, office_timeout)
        with pymupdf.open(src) as doc:
            if pages is None:
                indexes = list(range(doc.page_count))
            elif isinstance(pages, str):
                indexes = _page_ranges(pages, doc.page_count)
            else:
                indexes = [p - 1 for p in pages if 1 <= p <= doc.page_count]
            for idx in indexes:
                pix = doc[idx].get_pixmap(dpi=dpi)
                if fmt == "png":
                    data = pix.tobytes("png")
                elif fmt == "webp":
                    data = pix.pil_tobytes(format="WEBP", quality=quality)
                elif has_pil:
                    # Pillow's JPEG encoder is ~5x faster than MuPDF's.
                    data = pix.pil_tobytes(format="JPEG", quality=quality)
                else:
                    data = pix.tobytes("jpeg", jpg_quality=quality)
                yield idx + 1, data


def _office_to_pdf(file_path: str, outdir: str, timeout: int) -> str:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("Rendering office files needs LibreOffice (soffice) on PATH")
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, file_path],
            timeout=timeout, capture_output=True, check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"LibreOffice conversion failed: {exc}") from exc
    pdf = Path(outdir) / f"{Path(file_path).stem}.pdf"
    if not pdf.is_file():
        raise RuntimeError("LibreOffice conversion produced no PDF")
    return str(pdf)


__all__ = ["OFFICE_EXTENSIONS", "render_pages"]

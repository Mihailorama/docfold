"""Quality assessment utilities for EngineResult.

``quality_ok`` is a standalone check. To let the router retry on poor output,
pass ``quality_gate=default_quality_gate`` (or your own gate) to
``EngineRouter.process()``.

Example::

    from docfold.utils import quality_ok

    result = await router.process("invoice.pdf", engine_hint="pymupdf")
    if not quality_ok(result):
        result = await router.process("invoice.pdf", engine_hint="docling")
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from docfold.engines.base import EngineResult


@dataclass
class QualityThresholds:
    """Configurable thresholds for quality assessment.

    Thresholds can also be set via environment variables:

    - ``DOCFOLD_QUALITY_MIN_TEXT_LENGTH``
    - ``DOCFOLD_QUALITY_OCR_CONFIDENCE_MIN``
    - ``DOCFOLD_QUALITY_GIBBERISH_RATIO_MAX``
    """

    min_text_length: int = 50
    """Minimum chars to consider extraction successful."""

    ocr_confidence_min: float = 0.8
    """Minimum OCR confidence to accept."""

    gibberish_ratio_max: float = 0.3
    """Max ratio of non-printable / non-standard-unicode characters."""

    @classmethod
    def from_env(cls) -> QualityThresholds:
        """Create thresholds from environment variables, falling back to defaults."""
        defaults = cls()
        return cls(
            min_text_length=int(
                os.environ.get("DOCFOLD_QUALITY_MIN_TEXT_LENGTH", defaults.min_text_length)
            ),
            ocr_confidence_min=float(
                os.environ.get("DOCFOLD_QUALITY_OCR_CONFIDENCE_MIN", defaults.ocr_confidence_min)
            ),
            gibberish_ratio_max=float(
                os.environ.get(
                    "DOCFOLD_QUALITY_GIBBERISH_RATIO_MAX", defaults.gibberish_ratio_max
                )
            ),
        )


def quality_ok(result: EngineResult, thresholds: QualityThresholds | None = None) -> bool:
    """Check if an EngineResult meets minimum quality thresholds.

    Returns ``True`` if ALL of:

    1. ``result.content`` is not ``None`` and ``len(result.content.strip()) >= min_text_length``
    2. If ``result.confidence`` is not ``None``: ``confidence >= ocr_confidence_min``
    3. ``gibberish_ratio(result.content) <= gibberish_ratio_max``

    This is a standalone utility — NOT called automatically by EngineRouter.
    Consumers decide when and how to use it.
    """
    if thresholds is None:
        thresholds = QualityThresholds()

    # Check 1: minimum text length
    if not result.content or len(result.content.strip()) < thresholds.min_text_length:
        return False

    # Check 2: OCR confidence (only if engine reported it)
    if result.confidence is not None and result.confidence < thresholds.ocr_confidence_min:
        return False

    # Check 3: gibberish ratio
    if gibberish_ratio(result.content) > thresholds.gibberish_ratio_max:
        return False

    return True


def gibberish_ratio(text: str) -> float:
    """Calculate the ratio of non-printable / non-standard-unicode characters.

    Used to detect OCR garbage (e.g. ``"⌂☐▒▓░█"`` or control characters).

    Characters considered "gibberish":
    - Control characters (category ``Cc``) except common whitespace
    - Surrogate characters (``Cs``)
    - Unassigned characters (``Cn``)
    - Private-use characters (``Co``)
    - Box-drawing, block elements, and geometric shapes (U+2500–U+25FF)

    Returns 0.0 for empty strings.
    """
    if not text:
        return 0.0

    total = len(text)
    bad = 0
    whitespace = {"\n", "\r", "\t", " "}

    for ch in text:
        if ch in whitespace:
            continue
        cat = unicodedata.category(ch)
        # Control chars, surrogates, unassigned, private-use
        if cat in ("Cc", "Cs", "Cn", "Co"):
            bad += 1
        # Box-drawing, block elements, geometric shapes (common OCR garbage)
        elif _is_box_or_block(ch):
            bad += 1

    return bad / total


def _is_box_or_block(ch: str) -> bool:
    """Check if a character is a box-drawing or block element (common OCR artifacts)."""
    cp = ord(ch)
    # Box Drawing: U+2500–U+257F
    # Block Elements: U+2580–U+259F
    # Geometric Shapes: U+25A0–U+25FF (includes ☐, ▒, ▓, etc.)
    return 0x2500 <= cp <= 0x25FF


# ---------------------------------------------------------------------------
# Base64 page images and the default quality gate (DOCFOLD-11)
# ---------------------------------------------------------------------------

_BASE64_IMG_RE = re.compile(
    r"<(?:figure|img)[^>]*src\s*=\s*[\"']data:image/[^\"']+[\"'][^>]*/?>(?:</(?:figure|img)>)?",
    re.IGNORECASE | re.DOTALL,
)

_PAGED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "gif"}
_TEXT_LAYER_ENGINES = {"pymupdf"}
MIN_CHARS_PER_PAGE = 200
MAX_BASE64_RATIO = 0.9


def strip_base64_images(text: str) -> str:
    """Remove inline base64 ``<img>`` / ``<figure>`` tags.

    Some engines embed page images as base64 in HTML output instead of (or
    next to) the extracted text. They add no readable text.
    """
    return _BASE64_IMG_RE.sub("", text)


def base64_ratio(text: str) -> float:
    """Share of *text* taken by inline base64 images, in ``[0, 1]``."""
    if not text:
        return 0.0
    return 1.0 - len(strip_base64_images(text)) / len(text)


def _image_page_reason(file_path: str) -> str | None:
    """Flag PDFs whose text layer misses image content (scans, image tables)."""
    try:
        import pymupdf
    except ImportError:
        return None
    image_only = large_image = 0
    try:
        with pymupdf.open(file_path) as doc:
            for page in doc:
                images = page.get_images()
                if not images:
                    continue
                text_len = len(page.get_text().strip())
                if text_len < MIN_CHARS_PER_PAGE:
                    image_only += 1
                area = page.rect.width * page.rect.height
                img_area = sum(
                    abs(i["bbox"][2] - i["bbox"][0]) * abs(i["bbox"][3] - i["bbox"][1])
                    for i in page.get_image_info()
                )
                if area > 0 and img_area > 0.25 * area and text_len < 500:
                    large_image += 1
    except Exception:
        return None
    if image_only:
        return f"image_only_pages ({image_only} pages with images but <{MIN_CHARS_PER_PAGE} chars)"
    if large_image:
        return f"large_image_pages ({large_image} pages with >25% image area and <500 chars)"
    return None


def default_quality_gate(result: EngineResult, file_path: str) -> str | None:
    """Default gate for :meth:`EngineRouter.process`; returns a rejection reason or ``None``.

    Rejects when:

    1. more than 90% of the content is inline base64 images;
    2. PDFs/images: fewer than 200 real characters per page;
    3. :func:`quality_ok` fails (confidence below threshold, gibberish);
    4. a text-layer engine (``pymupdf``) read a PDF that has image-only pages
       or pages mostly covered by images (needs pymupdf installed).
    """
    content = result.content or ""
    ratio = base64_ratio(content)
    if ratio >= MAX_BASE64_RATIO:
        return f"base64_ratio ({ratio:.0%} of content is inline images)"
    real = strip_base64_images(content).strip()
    ext = Path(file_path).suffix.lstrip(".").lower()
    if ext in _PAGED_EXTENSIONS:
        pages = max(result.pages or 1, 1)
        if len(real) < pages * MIN_CHARS_PER_PAGE:
            return (
                f"low_avg_chars ({len(real)} chars / {pages} pages"
                f" = {len(real) // pages} < {MIN_CHARS_PER_PAGE})"
            )
    stripped = EngineResult(
        content=real, format=result.format, engine_name=result.engine_name,
        confidence=result.confidence,
    )
    if not quality_ok(stripped):
        return f"quality (confidence={result.confidence}, gibberish={gibberish_ratio(real):.2f})"
    if ext == "pdf" and result.engine_name in _TEXT_LAYER_ENGINES:
        return _image_page_reason(file_path)
    return None

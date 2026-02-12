"""Quality assessment utilities for EngineResult.

This is a **standalone utility** — NOT wired into ``EngineRouter.process()``.
Consumers call ``quality_ok(result)`` after getting an :class:`EngineResult`
and decide what to do.

Example::

    from docfold.utils import quality_ok

    result = await router.process("invoice.pdf", engine_hint="pymupdf")
    if not quality_ok(result):
        result = await router.process("invoice.pdf", engine_hint="docling")
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass

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

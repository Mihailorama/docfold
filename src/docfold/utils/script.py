"""Script detection for OCR engine routing.

Some engines break on some scripts (docling on Arabic/Hebrew), so the retry
chain depends on the script. :class:`ScriptRouting` plugs into
``EngineRouter.process(fallback_engines=ScriptRouting())``.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any

from docfold.engines.base import EngineResult

logger = logging.getLogger(__name__)


class ScriptHint(str, Enum):
    """Script family used for routing. ``arabic`` covers all RTL (Arabic, Hebrew)."""

    ARABIC = "arabic"
    CJK = "cjk"
    LATIN = "latin"
    CYRILLIC = "cyrillic"
    UNKNOWN = "unknown"


_RE_RTL = re.compile(r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_RE_CJK = re.compile(r"[\u4E00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]")
_RE_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_RE_LATIN = re.compile(r"[a-zA-Z\u00C0-\u024F]")
_PROBLEM_SHARE = 0.05

_OSD_SCRIPTS = {
    "Arabic": ScriptHint.ARABIC, "Hebrew": ScriptHint.ARABIC,
    "Han": ScriptHint.CJK, "Hangul": ScriptHint.CJK, "Katakana": ScriptHint.CJK,
    "Hiragana": ScriptHint.CJK, "Japanese": ScriptHint.CJK,
    "Cyrillic": ScriptHint.CYRILLIC, "Latin": ScriptHint.LATIN,
}
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "gif"}


def detect_script_hint(text: str, *, min_chars: int = 20) -> ScriptHint:
    """Script of *text* by Unicode ranges.

    RTL or CJK wins at >= 5% of letters (and at least 3 of them), since even a
    minority breaks some engines; otherwise Cyrillic vs Latin by majority.
    Fewer than *min_chars* letters gives ``UNKNOWN``.
    """
    if not text:
        return ScriptHint.UNKNOWN
    rtl = len(_RE_RTL.findall(text))
    cjk = len(_RE_CJK.findall(text))
    cyr = len(_RE_CYRILLIC.findall(text))
    lat = len(_RE_LATIN.findall(text))
    total = rtl + cjk + cyr + lat
    if total < min_chars:
        return ScriptHint.UNKNOWN
    if rtl >= 3 and rtl / total >= _PROBLEM_SHARE:
        return ScriptHint.ARABIC
    if cjk >= 3 and cjk / total >= _PROBLEM_SHARE:
        return ScriptHint.CJK
    return ScriptHint.CYRILLIC if cyr >= lat else ScriptHint.LATIN


def detect_script_from_image(image_path: str) -> ScriptHint:
    """Script of an image via Tesseract OSD (``--psm 0``); ``UNKNOWN`` on any failure."""
    try:
        import pytesseract

        osd = pytesseract.image_to_osd(image_path)
    except Exception as exc:  # noqa: BLE001 - missing binary, bad image, ...
        logger.debug("Tesseract OSD failed: %s", exc)
        return ScriptHint.UNKNOWN
    match = re.search(r"Script:\s*(\w+)", osd or "")
    return _OSD_SCRIPTS.get(match.group(1), ScriptHint.UNKNOWN) if match else ScriptHint.UNKNOWN


def detect_document_script(file_path: str, text: str = "") -> ScriptHint:
    """Script of a document: from *text* when it has enough letters, else OSD on page 1."""
    hint = detect_script_hint(text)
    if hint != ScriptHint.UNKNOWN:
        return hint
    ext = Path(file_path).suffix.lstrip(".").lower()
    if ext in _IMAGE_EXTENSIONS:
        return detect_script_from_image(file_path)
    if ext != "pdf":
        return ScriptHint.UNKNOWN
    try:
        import pymupdf

        with pymupdf.open(file_path) as doc:
            if not doc.page_count:
                return ScriptHint.UNKNOWN
            pix = doc[0].get_pixmap(dpi=150)
        fd, png = tempfile.mkstemp(suffix=".png")
        os.close(fd)
    except Exception as exc:  # noqa: BLE001
        logger.debug("First-page render failed: %s", exc)
        return ScriptHint.UNKNOWN
    try:
        pix.save(png)
        return detect_script_from_image(png)
    finally:
        os.unlink(png)


class ScriptRouting:
    """Retry chain by script, for ``EngineRouter.process(fallback_engines=...)``.

    Args:
        rules: script value -> engine list, e.g. ``{"arabic": ["marker"]}``.
        default: chain for scripts without a rule.
        max_pages: engine -> page limit; the engine is dropped for longer
            documents (e.g. a slow CPU backend).

    Returns ``(engines, {"script_hint": value})`` so the router records the
    script on the primary attempt.
    """

    def __init__(
        self,
        rules: dict[str, list[str]] | None = None,
        default: list[str] | None = None,
        max_pages: dict[str, int] | None = None,
    ) -> None:
        self.rules = {"arabic": ["marker"]} if rules is None else rules
        self.default = ["docling", "docling_serve", "marker"] if default is None else default
        self.max_pages = {"docling_serve": 5} if max_pages is None else max_pages

    def __call__(
        self, result: EngineResult | None, file_path: str,
    ) -> tuple[list[str], dict[str, Any]]:
        hint = detect_document_script(file_path, result.content if result else "")
        engines = self.rules.get(hint.value, self.default)
        pages = (result.pages if result else None) or 0
        engines = [e for e in engines if pages <= self.max_pages.get(e, pages)]
        return engines, {"script_hint": hint.value}

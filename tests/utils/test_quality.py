"""Tests for quality assessment utility."""

from __future__ import annotations

from docfold.engines.base import EngineResult, OutputFormat
from docfold.utils.quality import QualityThresholds, gibberish_ratio, quality_ok


def _make_result(
    content: str = "",
    confidence: float | None = None,
) -> EngineResult:
    """Helper to create an EngineResult for testing."""
    return EngineResult(
        content=content,
        format=OutputFormat.TEXT,
        engine_name="test",
        confidence=confidence,
    )


class TestQualityOk:
    def test_empty_content(self):
        result = _make_result(content="")
        assert quality_ok(result) is False

    def test_none_like_whitespace_content(self):
        result = _make_result(content="   \n\t  ")
        assert quality_ok(result) is False

    def test_short_content(self):
        """Content shorter than min_text_length (50 chars) → False."""
        result = _make_result(content="Hello world")  # 11 chars
        assert quality_ok(result) is False

    def test_content_exactly_at_threshold(self):
        """Content exactly at threshold → passes."""
        result = _make_result(content="A" * 50)
        assert quality_ok(result) is True

    def test_normal_content_no_confidence(self):
        """Normal content (500 chars), no confidence → True."""
        result = _make_result(content="Hello world. " * 40)  # ~520 chars
        assert quality_ok(result) is True

    def test_low_confidence(self):
        """Low confidence (0.3) → False."""
        result = _make_result(content="A" * 100, confidence=0.3)
        assert quality_ok(result) is False

    def test_high_confidence(self):
        """High confidence (0.9) → True."""
        result = _make_result(content="A" * 100, confidence=0.9)
        assert quality_ok(result) is True

    def test_confidence_exactly_at_threshold(self):
        """Confidence exactly at threshold (0.8) → passes."""
        result = _make_result(content="A" * 100, confidence=0.8)
        assert quality_ok(result) is True

    def test_confidence_just_below_threshold(self):
        """Confidence just below threshold → fails."""
        result = _make_result(content="A" * 100, confidence=0.79)
        assert quality_ok(result) is False

    def test_no_confidence_field(self):
        """confidence = None → confidence check skipped, passes if other checks pass."""
        result = _make_result(content="A" * 100, confidence=None)
        assert quality_ok(result) is True

    def test_high_gibberish_ratio(self):
        """Content with lots of box-drawing chars → False."""
        # 50% gibberish characters (box-drawing)
        gibberish = "A" * 50 + "\u2500" * 50 + "B" * 50  # 150 chars, 50 bad = 0.33
        result = _make_result(content=gibberish)
        assert quality_ok(result) is False

    def test_normal_text_low_gibberish(self):
        """Normal English text should have near-zero gibberish ratio."""
        text = "This is a normal document with standard English text. " * 10
        result = _make_result(content=text)
        assert quality_ok(result) is True


class TestQualityOkCustomThresholds:
    def test_custom_min_text_length(self):
        """Custom threshold: accept shorter text."""
        thresholds = QualityThresholds(min_text_length=10)
        result = _make_result(content="Hello world!")  # 12 chars
        assert quality_ok(result, thresholds) is True

    def test_custom_confidence_threshold(self):
        """Custom threshold: accept lower confidence."""
        thresholds = QualityThresholds(ocr_confidence_min=0.5)
        result = _make_result(content="A" * 100, confidence=0.6)
        assert quality_ok(result, thresholds) is True

    def test_custom_gibberish_threshold(self):
        """Custom threshold: accept higher gibberish ratio."""
        thresholds = QualityThresholds(gibberish_ratio_max=0.5)
        # ~33% gibberish → passes with 0.5 threshold
        content = "A" * 100 + "\u2500" * 50 + "B" * 50
        result = _make_result(content=content)
        assert quality_ok(result, thresholds) is True

    def test_strict_thresholds(self):
        """Very strict thresholds reject more content."""
        thresholds = QualityThresholds(
            min_text_length=200,
            ocr_confidence_min=0.95,
            gibberish_ratio_max=0.01,
        )
        result = _make_result(content="A" * 100, confidence=0.9)
        assert quality_ok(result, thresholds) is False  # Too short


class TestQualityThresholdsFromEnv:
    def test_env_vars_read(self, monkeypatch):
        monkeypatch.setenv("DOCFOLD_QUALITY_MIN_TEXT_LENGTH", "100")
        monkeypatch.setenv("DOCFOLD_QUALITY_OCR_CONFIDENCE_MIN", "0.9")
        monkeypatch.setenv("DOCFOLD_QUALITY_GIBBERISH_RATIO_MAX", "0.1")

        t = QualityThresholds.from_env()
        assert t.min_text_length == 100
        assert t.ocr_confidence_min == 0.9
        assert t.gibberish_ratio_max == 0.1

    def test_env_vars_defaults(self, monkeypatch):
        """Without env vars, defaults are used."""
        monkeypatch.delenv("DOCFOLD_QUALITY_MIN_TEXT_LENGTH", raising=False)
        monkeypatch.delenv("DOCFOLD_QUALITY_OCR_CONFIDENCE_MIN", raising=False)
        monkeypatch.delenv("DOCFOLD_QUALITY_GIBBERISH_RATIO_MAX", raising=False)

        t = QualityThresholds.from_env()
        assert t.min_text_length == 50
        assert t.ocr_confidence_min == 0.8
        assert t.gibberish_ratio_max == 0.3

    def test_partial_env_vars(self, monkeypatch):
        """Only some env vars set → partial override."""
        monkeypatch.setenv("DOCFOLD_QUALITY_MIN_TEXT_LENGTH", "200")
        monkeypatch.delenv("DOCFOLD_QUALITY_OCR_CONFIDENCE_MIN", raising=False)
        monkeypatch.delenv("DOCFOLD_QUALITY_GIBBERISH_RATIO_MAX", raising=False)

        t = QualityThresholds.from_env()
        assert t.min_text_length == 200
        assert t.ocr_confidence_min == 0.8  # default
        assert t.gibberish_ratio_max == 0.3  # default


class TestGibberishRatio:
    def test_empty_string(self):
        assert gibberish_ratio("") == 0.0

    def test_normal_text(self):
        ratio = gibberish_ratio("Hello, world! This is normal text.")
        assert ratio == 0.0

    def test_control_characters(self):
        """Control chars (except whitespace) count as gibberish."""
        text = "Hello\x00\x01\x02world"  # 3 control chars out of 13 total
        ratio = gibberish_ratio(text)
        assert ratio > 0.0

    def test_box_drawing_characters(self):
        """Box-drawing and block elements count as gibberish."""
        text = "A" * 50 + "\u2500\u2501\u2502\u2503" + "B" * 50  # 4 bad out of 104
        ratio = gibberish_ratio(text)
        assert 0.03 < ratio < 0.05

    def test_all_gibberish(self):
        text = "\u2500\u2580\u25A0\u25FF"  # all box/block/geometric
        ratio = gibberish_ratio(text)
        assert ratio == 1.0

    def test_whitespace_not_counted(self):
        """Spaces, tabs, newlines are NOT counted as gibberish."""
        text = "Hello world\n\tNext line"
        ratio = gibberish_ratio(text)
        assert ratio == 0.0

    def test_unicode_text_ok(self):
        """Normal unicode text (Russian, Chinese, etc.) is not gibberish."""
        text = "Привет мир! 你好世界！"
        ratio = gibberish_ratio(text)
        assert ratio == 0.0

    def test_mixed_content(self):
        """Mix of normal text and gibberish."""
        normal = "A" * 80
        bad = "\x00" * 20  # 20 control chars
        ratio = gibberish_ratio(normal + bad)
        assert abs(ratio - 0.2) < 0.01


# ---------------------------------------------------------------------------
# DOCFOLD-11: base64 helpers and the default quality gate
# ---------------------------------------------------------------------------

from docfold.utils.quality import (  # noqa: E402
    base64_ratio,
    default_quality_gate,
    strip_base64_images,
)

_IMG = '<img src="data:image/png;base64,' + "A" * 2000 + '" alt="p1"/>'


class TestBase64Helpers:
    def test_strip(self):
        fig = "<figure src='data:image/jpeg;base64,xx'></figure>"
        assert strip_base64_images(f"<p>hi</p>{_IMG}{fig}") == "<p>hi</p>"

    def test_regular_img_kept(self):
        html = '<img src="page1.png"/>'
        assert strip_base64_images(html) == html

    def test_ratio(self):
        assert base64_ratio("") == 0.0
        assert base64_ratio("plain") == 0.0
        assert base64_ratio(_IMG) == 1.0


def _gate_result(content, engine="docling", pages=1, confidence=None):
    return EngineResult(
        content=content, format=OutputFormat.HTML, engine_name=engine,
        pages=pages, confidence=confidence,
    )


class TestDefaultQualityGate:
    def test_low_chars_per_page(self, tmp_path):
        reason = default_quality_gate(_gate_result("a" * 300, pages=2), str(tmp_path / "x.pdf"))
        assert reason and reason.startswith("low_avg_chars")

    def test_enough_text_passes(self, tmp_path):
        assert default_quality_gate(_gate_result("word " * 100), str(tmp_path / "x.pdf")) is None

    def test_mostly_base64_rejected(self, tmp_path):
        content = "word " * 50 + _IMG * 10
        reason = default_quality_gate(_gate_result(content), str(tmp_path / "x.pdf"))
        assert reason and reason.startswith("base64_ratio")

    def test_low_confidence_rejected(self, tmp_path):
        reason = default_quality_gate(
            _gate_result("word " * 100, confidence=0.2), str(tmp_path / "x.pdf")
        )
        assert reason and reason.startswith("quality")

    def test_non_pdf_skips_page_density(self, tmp_path):
        memo = _gate_result("short memo, sixty characters of text here, fine fine.")
        assert default_quality_gate(memo, str(tmp_path / "m.docx")) is None

    def test_image_only_page_on_text_layer_engine(self, tmp_path):
        import pytest

        pymupdf = pytest.importorskip("pymupdf")
        path = tmp_path / "mixed.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Digital page. " * 40)
        page2 = doc.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 400), 0)
        pix.clear_with(200)
        page2.insert_image(page2.rect, pixmap=pix)
        doc.save(path)
        doc.close()
        text = "Digital page. " * 40
        res = _gate_result(text, engine="pymupdf", pages=1)
        reason = default_quality_gate(res, str(path))
        assert reason and reason.startswith("image_only_pages")
        # Same text from an OCR engine is judged on its output only.
        assert default_quality_gate(_gate_result(text, pages=1), str(path)) is None

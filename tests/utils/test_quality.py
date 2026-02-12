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

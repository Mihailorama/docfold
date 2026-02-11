"""Tests for the EngineRouter."""

import os
from unittest.mock import patch

import pytest

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat
from docfold.engines.router import EngineRouter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeEngine(DocumentEngine):
    def __init__(self, name: str, extensions: set[str], available: bool = True):
        self._name = name
        self._extensions = extensions
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_extensions(self) -> set[str]:
        return self._extensions

    def is_available(self) -> bool:
        return self._available

    async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
        return EngineResult(
            content=f"processed by {self._name}",
            format=output_format,
            engine_name=self._name,
        )


@pytest.fixture
def router():
    return EngineRouter([
        FakeEngine("docling", {"pdf", "docx", "png"}, available=True),
        FakeEngine("mineru", {"pdf"}, available=True),
        FakeEngine("marker", {"pdf", "docx"}, available=True),
        FakeEngine("pymupdf", {"pdf"}, available=True),
    ])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSelect:
    def test_explicit_hint(self, router):
        engine = router.select("test.pdf", engine_hint="mineru")
        assert engine.name == "mineru"

    def test_explicit_hint_unknown(self, router):
        with pytest.raises(ValueError, match="Unknown engine"):
            router.select("test.pdf", engine_hint="nonexistent")

    def test_explicit_hint_unavailable(self):
        r = EngineRouter([FakeEngine("broken", {"pdf"}, available=False)])
        with pytest.raises(RuntimeError, match="not available"):
            r.select("test.pdf", engine_hint="broken")

    def test_env_default(self, router):
        with patch.dict(os.environ, {"ENGINE_DEFAULT": "marker"}):
            engine = router.select("test.pdf")
            assert engine.name == "marker"

    def test_env_default_skipped_if_unavailable(self):
        r = EngineRouter([
            FakeEngine("broken", {"pdf"}, available=False),
            FakeEngine("fallback", {"pdf"}, available=True),
        ])
        with patch.dict(os.environ, {"ENGINE_DEFAULT": "broken"}):
            engine = r.select("test.pdf")
            assert engine.name == "fallback"

    def test_fallback_chain(self, router):
        # Without hints, should pick "docling" (first in fallback order)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ENGINE_DEFAULT", None)
            engine = router.select("test.pdf")
            assert engine.name == "docling"

    def test_extension_filter(self, router):
        # .png is only supported by docling
        engine = router.select("photo.png")
        assert engine.name == "docling"

    def test_no_suitable_engine(self):
        r = EngineRouter([FakeEngine("pdf_only", {"pdf"}, available=True)])
        with pytest.raises(ValueError, match="No available engine"):
            r.select("file.xyz")


class TestProcess:
    @pytest.mark.asyncio
    async def test_process_delegates(self, router):
        result = await router.process("test.pdf", engine_hint="mineru")
        assert result.engine_name == "mineru"
        assert "processed by mineru" in result.content


class TestCompare:
    @pytest.mark.asyncio
    async def test_compare_all(self, router):
        results = await router.compare("test.pdf")
        # All 4 engines support pdf
        assert len(results) == 4
        assert "docling" in results
        assert "mineru" in results

    @pytest.mark.asyncio
    async def test_compare_subset(self, router):
        results = await router.compare("test.pdf", engines=["docling", "pymupdf"])
        assert len(results) == 2


class TestExtensionPriority:
    """Test that the router picks the right engine based on file extension."""

    def test_docx_picks_docling_over_mineru(self):
        """MinerU is PDF-only; .docx should skip it."""
        r = EngineRouter([
            FakeEngine("mineru", {"pdf"}, available=True),
            FakeEngine("docling", {"pdf", "docx"}, available=True),
        ])
        engine = r.select("report.docx")
        assert engine.name == "docling"

    def test_png_prefers_paddleocr(self):
        """Image files should prefer OCR engines."""
        r = EngineRouter([
            FakeEngine("docling", {"pdf", "png"}, available=True),
            FakeEngine("paddleocr", {"png", "jpg", "pdf"}, available=True),
        ])
        engine = r.select("scan.png")
        assert engine.name == "paddleocr"

    def test_pdf_prefers_docling(self):
        """PDFs should prefer docling (first in PDF priority)."""
        r = EngineRouter([
            FakeEngine("paddleocr", {"png", "pdf"}, available=True),
            FakeEngine("docling", {"pdf", "docx"}, available=True),
        ])
        engine = r.select("document.pdf")
        assert engine.name == "docling"


class TestAllowedEngines:
    """Test that allowed_engines restricts engine selection."""

    def test_restricts_to_allowed(self):
        r = EngineRouter(
            engines=[
                FakeEngine("docling", {"pdf"}, available=True),
                FakeEngine("pymupdf", {"pdf"}, available=True),
            ],
            allowed_engines={"pymupdf"},
        )
        engine = r.select("test.pdf")
        assert engine.name == "pymupdf"

    def test_no_match_in_allowed(self):
        r = EngineRouter(
            engines=[
                FakeEngine("docling", {"pdf"}, available=True),
            ],
            allowed_engines={"pymupdf"},
        )
        with pytest.raises(ValueError, match="No available engine"):
            r.select("test.pdf")


class TestFallbackOrder:
    """Test that user-provided fallback_order overrides default priority."""

    def test_custom_order(self):
        r = EngineRouter(
            engines=[
                FakeEngine("docling", {"pdf"}, available=True),
                FakeEngine("pymupdf", {"pdf"}, available=True),
            ],
            fallback_order=["pymupdf", "docling"],
        )
        engine = r.select("test.pdf")
        assert engine.name == "pymupdf"

    def test_custom_order_skips_unavailable(self):
        r = EngineRouter(
            engines=[
                FakeEngine("first", {"pdf"}, available=False),
                FakeEngine("second", {"pdf"}, available=True),
            ],
            fallback_order=["first", "second"],
        )
        engine = r.select("test.pdf")
        assert engine.name == "second"


class TestListEngines:
    def test_list(self, router):
        engines = router.list_engines()
        assert len(engines) == 4
        names = {e["name"] for e in engines}
        assert names == {"docling", "mineru", "marker", "pymupdf"}

    def test_list_includes_capabilities(self, router):
        engines = router.list_engines()
        for e in engines:
            assert "capabilities" in e
            caps = e["capabilities"]
            assert "bounding_boxes" in caps
            assert "confidence" in caps
            assert "table_structure" in caps

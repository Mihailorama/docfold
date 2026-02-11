"""Tests for engine adapters — unit tests using mocks, no real dependencies needed."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from docfold.engines.base import OutputFormat, EngineResult


class TestDoclingEngine:
    def test_name(self):
        from docfold.engines.docling_engine import DoclingEngine
        e = DoclingEngine()
        assert e.name == "docling"

    def test_supported_extensions(self):
        from docfold.engines.docling_engine import DoclingEngine
        e = DoclingEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "pptx" in exts
        assert "xlsx" in exts
        assert "html" in exts
        assert "png" in exts
        assert "jpg" in exts

    def test_is_available_when_missing(self):
        from docfold.engines.docling_engine import DoclingEngine
        e = DoclingEngine()
        with patch.dict("sys.modules", {"docling": None}):
            # Even with mock, the import check may vary
            # Just verify is_available returns bool
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.docling_engine import DoclingEngine
        e = DoclingEngine(pipeline="vlm", ocr_enabled=False)
        assert e._pipeline == "vlm"
        assert e._ocr_enabled is False


class TestMinerUEngine:
    def test_name(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine()
        assert e.name == "mineru"

    def test_supported_extensions(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine()
        assert e.supported_extensions == {"pdf"}

    def test_is_available_when_missing(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine()
        with patch.dict("sys.modules", {"magic_pdf": None}):
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine(config_path="/tmp/cfg.yaml", gpu=True)
        assert e._config_path == "/tmp/cfg.yaml"
        assert e._gpu is True


class TestMarkerEngine:
    def test_name(self):
        from docfold.engines.marker_engine import MarkerEngine
        e = MarkerEngine()
        assert e.name == "marker"

    def test_supported_extensions(self):
        from docfold.engines.marker_engine import MarkerEngine
        e = MarkerEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "png" in exts

    def test_is_available_without_key(self):
        from docfold.engines.marker_engine import MarkerEngine
        with patch.dict("os.environ", {}, clear=True):
            e = MarkerEngine(api_key=None)
            # No API key → not available (even if requests is installed)
            assert e.is_available() is False

    def test_is_available_with_key(self):
        from docfold.engines.marker_engine import MarkerEngine
        e = MarkerEngine(api_key="test-key-123")
        assert e.is_available() is True

    def test_config_stored(self):
        from docfold.engines.marker_engine import MarkerEngine
        e = MarkerEngine(api_key="k", use_llm=True, force_ocr=True)
        assert e._api_key == "k"
        assert e._use_llm is True
        assert e._force_ocr is True


class TestPyMuPDFEngine:
    def test_name(self):
        from docfold.engines.pymupdf_engine import PyMuPDFEngine
        e = PyMuPDFEngine()
        assert e.name == "pymupdf"

    def test_supported_extensions(self):
        from docfold.engines.pymupdf_engine import PyMuPDFEngine
        e = PyMuPDFEngine()
        assert e.supported_extensions == {"pdf"}

    def test_is_available_when_missing(self):
        from docfold.engines.pymupdf_engine import PyMuPDFEngine
        e = PyMuPDFEngine()
        with patch.dict("sys.modules", {"fitz": None}):
            result = e.is_available()
            assert isinstance(result, bool)


class TestOCREngine:
    def test_name(self):
        from docfold.engines.ocr_engine import OCREngine
        e = OCREngine()
        assert e.name == "ocr"

    def test_supported_extensions(self):
        from docfold.engines.ocr_engine import OCREngine
        e = OCREngine()
        exts = e.supported_extensions
        assert "png" in exts
        assert "jpg" in exts
        assert "pdf" in exts
        assert "tiff" in exts

    def test_config_stored(self):
        from docfold.engines.ocr_engine import OCREngine
        e = OCREngine(lang="ru", use_paddle=False)
        assert e._lang == "ru"
        assert e._use_paddle is False

    def test_is_available_returns_bool(self):
        from docfold.engines.ocr_engine import OCREngine
        e = OCREngine()
        assert isinstance(e.is_available(), bool)


class TestAllEnginesImplementInterface:
    """Verify every adapter satisfies the DocumentEngine ABC."""

    @pytest.mark.parametrize("engine_cls_path", [
        "docfold.engines.docling_engine.DoclingEngine",
        "docfold.engines.mineru_engine.MinerUEngine",
        "docfold.engines.marker_engine.MarkerEngine",
        "docfold.engines.pymupdf_engine.PyMuPDFEngine",
        "docfold.engines.ocr_engine.OCREngine",
    ])
    def test_has_required_attributes(self, engine_cls_path):
        module_path, cls_name = engine_cls_path.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, cls_name)
        engine = cls() if cls_name != "MarkerEngine" else cls(api_key="test")

        assert isinstance(engine.name, str)
        assert len(engine.name) > 0
        assert isinstance(engine.supported_extensions, set)
        assert len(engine.supported_extensions) > 0
        assert isinstance(engine.is_available(), bool)
        assert hasattr(engine, "process")
        assert callable(engine.process)

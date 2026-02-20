"""Tests for engine adapters — unit tests using mocks, no real dependencies needed."""

from unittest.mock import patch

import pytest

from docfold.engines.base import EngineCapabilities


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
        import types
        from unittest.mock import patch

        from docfold.engines.marker_engine import MarkerEngine
        e = MarkerEngine(api_key="test-key-123")
        with patch.dict("sys.modules", {"requests": types.ModuleType("requests")}):
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


class TestPaddleOCREngine:
    def test_name(self):
        from docfold.engines.paddleocr_engine import PaddleOCREngine
        e = PaddleOCREngine()
        assert e.name == "paddleocr"

    def test_supported_extensions(self):
        from docfold.engines.paddleocr_engine import PaddleOCREngine
        e = PaddleOCREngine()
        exts = e.supported_extensions
        assert "png" in exts
        assert "jpg" in exts
        assert "pdf" in exts
        assert "tiff" in exts

    def test_config_stored(self):
        from docfold.engines.paddleocr_engine import PaddleOCREngine
        e = PaddleOCREngine(lang="ru")
        assert e._lang == "ru"

    def test_is_available_returns_bool(self):
        from docfold.engines.paddleocr_engine import PaddleOCREngine
        e = PaddleOCREngine()
        assert isinstance(e.is_available(), bool)


class TestTesseractEngine:
    def test_name(self):
        from docfold.engines.tesseract_engine import TesseractEngine
        e = TesseractEngine()
        assert e.name == "tesseract"

    def test_supported_extensions(self):
        from docfold.engines.tesseract_engine import TesseractEngine
        e = TesseractEngine()
        exts = e.supported_extensions
        assert "png" in exts
        assert "jpg" in exts
        assert "pdf" in exts
        assert "tiff" in exts

    def test_config_stored(self):
        from docfold.engines.tesseract_engine import TesseractEngine
        e = TesseractEngine(lang="rus")
        assert e._lang == "rus"

    def test_is_available_returns_bool(self):
        from docfold.engines.tesseract_engine import TesseractEngine
        e = TesseractEngine()
        assert isinstance(e.is_available(), bool)


class TestEasyOCREngine:
    def test_name(self):
        from docfold.engines.easyocr_engine import EasyOCREngine
        e = EasyOCREngine()
        assert e.name == "easyocr"

    def test_supported_extensions(self):
        from docfold.engines.easyocr_engine import EasyOCREngine
        e = EasyOCREngine()
        exts = e.supported_extensions
        assert "png" in exts
        assert "jpg" in exts
        assert "pdf" in exts
        assert "tiff" in exts

    def test_config_stored(self):
        from docfold.engines.easyocr_engine import EasyOCREngine
        e = EasyOCREngine(lang=["ru", "en"], gpu=False)
        assert e._lang == ["ru", "en"]
        assert e._gpu is False

    def test_config_defaults(self):
        from docfold.engines.easyocr_engine import EasyOCREngine
        e = EasyOCREngine()
        assert e._lang == ["en"]
        assert e._gpu is True

    def test_is_available_returns_bool(self):
        from docfold.engines.easyocr_engine import EasyOCREngine
        e = EasyOCREngine()
        assert isinstance(e.is_available(), bool)

    def test_capabilities(self):
        from docfold.engines.easyocr_engine import EasyOCREngine
        e = EasyOCREngine()
        caps = e.capabilities
        assert caps.confidence is True


class TestUnstructuredEngine:
    def test_name(self):
        from docfold.engines.unstructured_engine import UnstructuredEngine
        e = UnstructuredEngine()
        assert e.name == "unstructured"

    def test_supported_extensions(self):
        from docfold.engines.unstructured_engine import UnstructuredEngine
        e = UnstructuredEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "html" in exts
        assert "png" in exts
        assert "eml" in exts

    def test_config_stored(self):
        from docfold.engines.unstructured_engine import UnstructuredEngine
        e = UnstructuredEngine(strategy="hi_res")
        assert e._strategy == "hi_res"

    def test_is_available_returns_bool(self):
        from docfold.engines.unstructured_engine import UnstructuredEngine
        e = UnstructuredEngine()
        assert isinstance(e.is_available(), bool)


class TestLlamaParseEngine:
    def test_name(self):
        from docfold.engines.llamaparse_engine import LlamaParseEngine
        e = LlamaParseEngine()
        assert e.name == "llamaparse"

    def test_supported_extensions(self):
        from docfold.engines.llamaparse_engine import LlamaParseEngine
        e = LlamaParseEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "pptx" in exts

    def test_is_available_without_key(self):
        from docfold.engines.llamaparse_engine import LlamaParseEngine
        e = LlamaParseEngine(api_key=None)
        # Without an API key, even if the library is installed, should not be available
        # (or if library is missing, also not available)
        assert e.is_available() is False

    def test_config_stored(self):
        from docfold.engines.llamaparse_engine import LlamaParseEngine
        e = LlamaParseEngine(api_key="test-key", result_type="html")
        assert e._api_key == "test-key"
        assert e._result_type == "html"


class TestMistralOCREngine:
    def test_name(self):
        from docfold.engines.mistral_ocr_engine import MistralOCREngine
        e = MistralOCREngine()
        assert e.name == "mistral_ocr"

    def test_supported_extensions(self):
        from docfold.engines.mistral_ocr_engine import MistralOCREngine
        e = MistralOCREngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "png" in exts
        assert "jpg" in exts

    def test_is_available_without_key(self):
        from docfold.engines.mistral_ocr_engine import MistralOCREngine
        e = MistralOCREngine(api_key=None)
        assert e.is_available() is False

    def test_config_stored(self):
        from docfold.engines.mistral_ocr_engine import MistralOCREngine
        e = MistralOCREngine(api_key="mk", model="pixtral-large")
        assert e._api_key == "mk"
        assert e._model == "pixtral-large"


class TestZeroxEngine:
    def test_name(self):
        from docfold.engines.zerox_engine import ZeroxEngine
        e = ZeroxEngine()
        assert e.name == "zerox"

    def test_supported_extensions(self):
        from docfold.engines.zerox_engine import ZeroxEngine
        e = ZeroxEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "png" in exts

    def test_config_stored(self):
        from docfold.engines.zerox_engine import ZeroxEngine
        e = ZeroxEngine(model="claude-3-opus", provider="anthropic")
        assert e._model == "claude-3-opus"
        assert e._provider == "anthropic"

    def test_is_available_returns_bool(self):
        from docfold.engines.zerox_engine import ZeroxEngine
        e = ZeroxEngine()
        assert isinstance(e.is_available(), bool)


class TestTextractEngine:
    def test_name(self):
        from docfold.engines.textract_engine import TextractEngine
        e = TextractEngine()
        assert e.name == "textract"

    def test_supported_extensions(self):
        from docfold.engines.textract_engine import TextractEngine
        e = TextractEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "png" in exts
        assert "jpg" in exts

    def test_config_stored(self):
        from docfold.engines.textract_engine import TextractEngine
        e = TextractEngine(region_name="eu-west-1")
        assert e._region_name == "eu-west-1"

    def test_capabilities(self):
        from docfold.engines.textract_engine import TextractEngine
        e = TextractEngine()
        caps = e.capabilities
        assert caps.bounding_boxes is True
        assert caps.confidence is True
        assert caps.table_structure is True
        assert caps.reading_order is True

    def test_is_available_returns_bool(self):
        from docfold.engines.textract_engine import TextractEngine
        e = TextractEngine()
        assert isinstance(e.is_available(), bool)


class TestGoogleDocAIEngine:
    def test_name(self):
        from docfold.engines.google_docai_engine import GoogleDocAIEngine
        e = GoogleDocAIEngine()
        assert e.name == "google_docai"

    def test_supported_extensions(self):
        from docfold.engines.google_docai_engine import GoogleDocAIEngine
        e = GoogleDocAIEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "png" in exts
        assert "jpg" in exts

    def test_is_available_without_config(self):
        from docfold.engines.google_docai_engine import GoogleDocAIEngine
        e = GoogleDocAIEngine(project_id=None, processor_id=None)
        # Without project_id and processor_id → not available
        assert e.is_available() is False

    def test_config_stored(self):
        from docfold.engines.google_docai_engine import GoogleDocAIEngine
        e = GoogleDocAIEngine(project_id="proj", location="eu", processor_id="abc")
        assert e._project_id == "proj"
        assert e._location == "eu"
        assert e._processor_id == "abc"

    def test_capabilities(self):
        from docfold.engines.google_docai_engine import GoogleDocAIEngine
        e = GoogleDocAIEngine()
        caps = e.capabilities
        assert caps.bounding_boxes is True
        assert caps.confidence is True
        assert caps.heading_detection is True


class TestAzureDocIntEngine:
    def test_name(self):
        from docfold.engines.azure_docint_engine import AzureDocIntEngine
        e = AzureDocIntEngine()
        assert e.name == "azure_docint"

    def test_supported_extensions(self):
        from docfold.engines.azure_docint_engine import AzureDocIntEngine
        e = AzureDocIntEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "xlsx" in exts
        assert "pptx" in exts
        assert "png" in exts

    def test_is_available_without_credentials(self):
        from docfold.engines.azure_docint_engine import AzureDocIntEngine
        e = AzureDocIntEngine(endpoint=None, key=None)
        assert e.is_available() is False

    def test_config_stored(self):
        from docfold.engines.azure_docint_engine import AzureDocIntEngine
        e = AzureDocIntEngine(
            endpoint="https://example.cognitiveservices.azure.com/",
            key="test-key",
            model_id="prebuilt-read",
        )
        assert e._endpoint == "https://example.cognitiveservices.azure.com/"
        assert e._key == "test-key"
        assert e._model_id == "prebuilt-read"

    def test_capabilities(self):
        from docfold.engines.azure_docint_engine import AzureDocIntEngine
        e = AzureDocIntEngine()
        caps = e.capabilities
        assert caps.bounding_boxes is True
        assert caps.confidence is True
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True


class TestNougatEngine:
    def test_name(self):
        from docfold.engines.nougat_engine import NougatEngine
        e = NougatEngine()
        assert e.name == "nougat"

    def test_supported_extensions(self):
        from docfold.engines.nougat_engine import NougatEngine
        e = NougatEngine()
        assert e.supported_extensions == {"pdf"}

    def test_is_available_when_missing(self):
        from docfold.engines.nougat_engine import NougatEngine
        e = NougatEngine()
        with patch.dict("sys.modules", {"nougat": None}):
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.nougat_engine import NougatEngine
        e = NougatEngine(model="facebook/nougat-base", batch_size=4, no_skipping=True)
        assert e._model == "facebook/nougat-base"
        assert e._batch_size == 4
        assert e._no_skipping is True

    def test_capabilities(self):
        from docfold.engines.nougat_engine import NougatEngine
        caps = NougatEngine().capabilities
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True
        assert caps.bounding_boxes is False
        assert caps.confidence is False


class TestSuryaEngine:
    def test_name(self):
        from docfold.engines.surya_engine import SuryaEngine
        e = SuryaEngine()
        assert e.name == "surya"

    def test_supported_extensions(self):
        from docfold.engines.surya_engine import SuryaEngine
        e = SuryaEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "png" in exts
        assert "jpg" in exts
        assert "jpeg" in exts
        assert "tiff" in exts
        assert "webp" in exts

    def test_is_available_when_missing(self):
        from docfold.engines.surya_engine import SuryaEngine
        e = SuryaEngine()
        with patch.dict("sys.modules", {"surya": None}):
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.surya_engine import SuryaEngine
        e = SuryaEngine(langs=["en", "ru"])
        assert e._langs == ["en", "ru"]

    def test_capabilities(self):
        from docfold.engines.surya_engine import SuryaEngine
        caps = SuryaEngine().capabilities
        assert caps.bounding_boxes is True
        assert caps.confidence is True
        assert caps.images is True
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True


class TestEngineCapabilities:
    """Verify capabilities are declared correctly on engines with non-default values."""

    def test_docling_capabilities(self):
        from docfold.engines.docling_engine import DoclingEngine
        caps = DoclingEngine().capabilities
        assert caps.bounding_boxes is True
        assert caps.images is True
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True

    def test_marker_capabilities(self):
        from docfold.engines.marker_engine import MarkerEngine
        caps = MarkerEngine(api_key="k").capabilities
        assert caps.bounding_boxes is True
        assert caps.images is True
        assert caps.table_structure is True
        assert caps.heading_detection is True

    def test_paddleocr_capabilities(self):
        from docfold.engines.paddleocr_engine import PaddleOCREngine
        caps = PaddleOCREngine().capabilities
        assert caps.confidence is True
        assert caps.bounding_boxes is False

    def test_pymupdf_default_capabilities(self):
        from docfold.engines.pymupdf_engine import PyMuPDFEngine
        caps = PyMuPDFEngine().capabilities
        assert caps.bounding_boxes is False
        assert caps.confidence is False
        assert caps.table_structure is False

    def test_all_engines_have_capabilities(self):
        """Every engine must return an EngineCapabilities instance."""
        from docfold.engines.docling_engine import DoclingEngine
        from docfold.engines.pymupdf_engine import PyMuPDFEngine
        from docfold.engines.tesseract_engine import TesseractEngine
        for cls in [DoclingEngine, PyMuPDFEngine, TesseractEngine]:
            caps = cls().capabilities
            assert isinstance(caps, EngineCapabilities)


class TestAllEnginesImplementInterface:
    """Verify every adapter satisfies the DocumentEngine ABC."""

    @pytest.mark.parametrize("engine_cls_path", [
        "docfold.engines.docling_engine.DoclingEngine",
        "docfold.engines.mineru_engine.MinerUEngine",
        "docfold.engines.marker_engine.MarkerEngine",
        "docfold.engines.pymupdf_engine.PyMuPDFEngine",
        "docfold.engines.paddleocr_engine.PaddleOCREngine",
        "docfold.engines.tesseract_engine.TesseractEngine",
        "docfold.engines.easyocr_engine.EasyOCREngine",
        "docfold.engines.unstructured_engine.UnstructuredEngine",
        "docfold.engines.llamaparse_engine.LlamaParseEngine",
        "docfold.engines.mistral_ocr_engine.MistralOCREngine",
        "docfold.engines.zerox_engine.ZeroxEngine",
        "docfold.engines.textract_engine.TextractEngine",
        "docfold.engines.google_docai_engine.GoogleDocAIEngine",
        "docfold.engines.azure_docint_engine.AzureDocIntEngine",
        "docfold.engines.nougat_engine.NougatEngine",
        "docfold.engines.surya_engine.SuryaEngine",
    ])
    def test_has_required_attributes(self, engine_cls_path):
        module_path, cls_name = engine_cls_path.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, cls_name)
        _needs_key = {"MarkerEngine", "LlamaParseEngine", "MistralOCREngine"}
        engine = cls(api_key="test") if cls_name in _needs_key else cls()

        assert isinstance(engine.name, str)
        assert len(engine.name) > 0
        assert isinstance(engine.supported_extensions, set)
        assert len(engine.supported_extensions) > 0
        assert isinstance(engine.is_available(), bool)
        assert hasattr(engine, "process")
        assert callable(engine.process)
        assert isinstance(engine.capabilities, EngineCapabilities)

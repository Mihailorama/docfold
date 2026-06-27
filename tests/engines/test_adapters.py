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
        with patch.dict("sys.modules", {"mineru": None}):
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine(config_path="/tmp/cfg.yaml", gpu=True)
        assert e._config_path == "/tmp/cfg.yaml"
        assert e._gpu is True

    def test_default_backend_is_pipeline(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine()
        assert e._backend == "pipeline"

    def test_backend_config_stored(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine(backend="vlm", parse_method="ocr")
        assert e._backend == "vlm"
        assert e._parse_method == "ocr"

    def test_capabilities(self):
        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine()
        caps = e.capabilities
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True
        assert caps.bounding_boxes is False
        assert caps.confidence is False

    def test_is_available_when_installed(self):
        """When mineru is importable, is_available returns True."""
        from unittest.mock import MagicMock, patch

        from docfold.engines.mineru_engine import MinerUEngine
        e = MinerUEngine()
        with patch.dict("sys.modules", {"mineru": MagicMock()}):
            result = e.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_process_returns_engine_result(self, tmp_path):
        """MinerU 2.x engine processes a PDF via do_parse and returns a result."""
        import os
        from unittest.mock import patch

        from docfold.engines.base import EngineResult, OutputFormat
        from docfold.engines.mineru_engine import MinerUEngine

        def fake_do_parse(output_dir, pdf_file_names, *args, **kwargs):
            # Mimic MinerU 2.x pipeline layout: output_dir/<name>/<parse_method>/<name>.md
            name = pdf_file_names[0]
            parse_method = kwargs.get("parse_method", "auto")
            md_dir = os.path.join(output_dir, name, parse_method)
            os.makedirs(md_dir, exist_ok=True)
            with open(os.path.join(md_dir, f"{name}.md"), "w") as fh:
                fh.write("# Hello\n\nExtracted content")

        with patch("docfold.engines.mineru_engine._ensure_imports"), \
             patch("docfold.engines.mineru_engine.read_fn", return_value=b"%PDF-1.4"), \
             patch("docfold.engines.mineru_engine.do_parse", side_effect=fake_do_parse):
            e = MinerUEngine()
            pdf = tmp_path / "doc.pdf"
            pdf.write_bytes(b"%PDF-1.4 minimal")
            result = await e.process(str(pdf), OutputFormat.MARKDOWN)
            assert isinstance(result, EngineResult)
            assert result.engine_name == "mineru"
            assert result.content == "# Hello\n\nExtracted content"
            assert result.format == OutputFormat.MARKDOWN
            assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_process_json_output_format(self, tmp_path):
        """MinerU returns content_list JSON when output_format is JSON."""
        import os
        from unittest.mock import patch

        from docfold.engines.base import OutputFormat
        from docfold.engines.mineru_engine import MinerUEngine

        def fake_do_parse(output_dir, pdf_file_names, *args, **kwargs):
            name = pdf_file_names[0]
            parse_method = kwargs.get("parse_method", "auto")
            md_dir = os.path.join(output_dir, name, parse_method)
            os.makedirs(md_dir, exist_ok=True)
            with open(os.path.join(md_dir, f"{name}_content_list.json"), "w") as fh:
                fh.write('[{"type": "text", "text": "hello"}]')

        with patch("docfold.engines.mineru_engine._ensure_imports"), \
             patch("docfold.engines.mineru_engine.read_fn", return_value=b"%PDF-1.4"), \
             patch("docfold.engines.mineru_engine.do_parse", side_effect=fake_do_parse):
            e = MinerUEngine()
            pdf = tmp_path / "doc.pdf"
            pdf.write_bytes(b"%PDF-1.4 minimal")
            result = await e.process(str(pdf), OutputFormat.JSON)
            assert result.format == OutputFormat.JSON
            assert "text" in result.content

    @pytest.mark.asyncio
    async def test_process_forwards_page_range_and_lang(self, tmp_path):
        """MinerU forwards start_page/end_page as start_page_id/end_page_id and lang."""
        import os
        from unittest.mock import MagicMock, patch

        from docfold.engines.base import OutputFormat
        from docfold.engines.mineru_engine import MinerUEngine

        def fake_do_parse(output_dir, pdf_file_names, *args, **kwargs):
            name = pdf_file_names[0]
            parse_method = kwargs.get("parse_method", "auto")
            md_dir = os.path.join(output_dir, name, parse_method)
            os.makedirs(md_dir, exist_ok=True)
            with open(os.path.join(md_dir, f"{name}.md"), "w") as fh:
                fh.write("page content")

        mock_do_parse = MagicMock(side_effect=fake_do_parse)
        with patch("docfold.engines.mineru_engine._ensure_imports"), \
             patch("docfold.engines.mineru_engine.read_fn", return_value=b"%PDF-1.4"), \
             patch("docfold.engines.mineru_engine.do_parse", mock_do_parse):
            e = MinerUEngine()
            pdf = tmp_path / "doc.pdf"
            pdf.write_bytes(b"%PDF-1.4 minimal")
            await e.process(
                str(pdf), OutputFormat.MARKDOWN,
                start_page=2, end_page=5, lang="ru",
            )
            kwargs = mock_do_parse.call_args.kwargs
            assert kwargs["start_page_id"] == 2
            assert kwargs["end_page_id"] == 5
            assert kwargs["p_lang_list"] == ["ru"]
            assert kwargs["backend"] == "pipeline"

    @pytest.mark.asyncio
    async def test_process_vlm_backend_reads_vlm_subdir(self, tmp_path):
        """With backend='vlm', output is read from the 'vlm' subdirectory."""
        import os
        from unittest.mock import MagicMock, patch

        from docfold.engines.base import OutputFormat
        from docfold.engines.mineru_engine import MinerUEngine

        def fake_do_parse(output_dir, pdf_file_names, *args, **kwargs):
            name = pdf_file_names[0]
            md_dir = os.path.join(output_dir, name, "vlm")
            os.makedirs(md_dir, exist_ok=True)
            with open(os.path.join(md_dir, f"{name}.md"), "w") as fh:
                fh.write("vlm content")

        mock_do_parse = MagicMock(side_effect=fake_do_parse)
        with patch("docfold.engines.mineru_engine._ensure_imports"), \
             patch("docfold.engines.mineru_engine.read_fn", return_value=b"%PDF-1.4"), \
             patch("docfold.engines.mineru_engine.do_parse", mock_do_parse):
            e = MinerUEngine(backend="vlm")
            pdf = tmp_path / "doc.pdf"
            pdf.write_bytes(b"%PDF-1.4 minimal")
            result = await e.process(str(pdf), OutputFormat.MARKDOWN)
            assert result.content == "vlm content"
            assert mock_do_parse.call_args.kwargs["backend"] == "vlm"


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
        e = MarkerEngine(api_key="k", mode="fast", paginate=True)
        assert e._api_key == "k"
        assert e._defaults["mode"] == "fast"
        assert e._defaults["paginate"] is True


class TestMarkerLocalEngine:
    def test_name(self):
        from docfold.engines.marker_local_engine import MarkerLocalEngine
        e = MarkerLocalEngine()
        assert e.name == "marker_local"

    def test_supported_extensions(self):
        from docfold.engines.marker_local_engine import MarkerLocalEngine
        e = MarkerLocalEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "png" in exts

    def test_is_available_when_missing(self):
        from docfold.engines.marker_local_engine import MarkerLocalEngine
        e = MarkerLocalEngine()
        with patch.dict("sys.modules", {"marker": None}):
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.marker_local_engine import MarkerLocalEngine
        e = MarkerLocalEngine(force_ocr=True)
        assert e._force_ocr is True

    def test_capabilities(self):
        from docfold.engines.marker_local_engine import MarkerLocalEngine
        e = MarkerLocalEngine()
        caps = e.capabilities
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.bounding_boxes is False
        assert caps.confidence is False

    @pytest.mark.asyncio
    async def test_process_returns_engine_result(self):
        """MarkerLocal engine processes a PDF and returns a valid EngineResult."""
        import os
        import tempfile
        from unittest.mock import MagicMock, patch

        from docfold.engines.base import EngineResult, OutputFormat
        from docfold.engines.marker_local_engine import MarkerLocalEngine

        mock_rendered = MagicMock()
        mock_converter = MagicMock(return_value=mock_rendered)

        ml_prefix = "docfold.engines.marker_local_engine"
        rendered_val = ("# Extracted\n\nContent", {}, {})
        with patch(f"{ml_prefix}._ensure_imports"), \
             patch(f"{ml_prefix}.PdfConverter", return_value=mock_converter), \
             patch(f"{ml_prefix}.create_model_dict", return_value={}), \
             patch(f"{ml_prefix}.text_from_rendered", return_value=rendered_val):
            e = MarkerLocalEngine()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4 minimal")
            try:
                result = await e.process(f.name, OutputFormat.MARKDOWN)
                assert isinstance(result, EngineResult)
                assert result.engine_name == "marker_local"
                assert result.content == "# Extracted\n\nContent"
                assert result.format == OutputFormat.MARKDOWN
                assert result.processing_time_ms >= 0
            finally:
                os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_process_json_output(self):
        """MarkerLocal returns JSON wrapping markdown content."""
        import json
        import os
        import tempfile
        from unittest.mock import MagicMock, patch

        from docfold.engines.base import OutputFormat
        from docfold.engines.marker_local_engine import MarkerLocalEngine

        mock_rendered = MagicMock()
        mock_converter = MagicMock(return_value=mock_rendered)

        ml_prefix = "docfold.engines.marker_local_engine"
        rendered_val = ("hello", {}, {"img.png": b"data"})
        with patch(f"{ml_prefix}._ensure_imports"), \
             patch(f"{ml_prefix}.PdfConverter", return_value=mock_converter), \
             patch(f"{ml_prefix}.create_model_dict", return_value={}), \
             patch(f"{ml_prefix}.text_from_rendered", return_value=rendered_val):
            e = MarkerLocalEngine()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4 minimal")
            try:
                result = await e.process(f.name, OutputFormat.JSON)
                assert result.format == OutputFormat.JSON
                parsed = json.loads(result.content)
                assert parsed["markdown"] == "hello"
                assert "img.png" in parsed["images"]
            finally:
                os.unlink(f.name)


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

    def test_capabilities_declare_bounding_boxes(self):
        from docfold.engines.pymupdf_engine import PyMuPDFEngine
        e = PyMuPDFEngine()
        assert e.capabilities.bounding_boxes is True

    @pytest.mark.asyncio
    async def test_process_returns_bounding_boxes(self, tmp_path):
        """PyMuPDF should return bounding boxes for a simple PDF."""
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")

        from docfold.engines.base import OutputFormat
        from docfold.engines.pymupdf_engine import PyMuPDFEngine

        # Create a minimal PDF with text
        pdf_path = str(tmp_path / "test.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World", fontsize=12)
        doc.save(pdf_path)
        doc.close()

        engine = PyMuPDFEngine()
        result = await engine.process(pdf_path, output_format=OutputFormat.HTML)

        assert result.pages == 1
        assert result.bounding_boxes is not None
        assert len(result.bounding_boxes) > 0
        bbox = result.bounding_boxes[0]
        assert "bbox" in bbox
        assert "page" in bbox
        assert bbox["page"] == 1
        assert "type" in bbox
        assert "text" in bbox

    @pytest.mark.asyncio
    async def test_bboxes_include_page_dimensions(self, tmp_path):
        """Every bbox must include page_width/page_height for frontend normalization.

        Without page dimensions, the frontend cannot normalize absolute PDF
        point coordinates to 0-1 range, causing giant overlapping overlays.
        """
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")

        from docfold.engines.base import OutputFormat
        from docfold.engines.pymupdf_engine import PyMuPDFEngine

        pdf_path = str(tmp_path / "test.pdf")
        doc = fitz.open()
        # Letter size: 612 x 792 points
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), "Hello World", fontsize=12)
        page.insert_text((72, 200), "Second block", fontsize=12)
        doc.save(pdf_path)
        doc.close()

        engine = PyMuPDFEngine()
        result = await engine.process(pdf_path, output_format=OutputFormat.MARKDOWN)

        assert result.bounding_boxes is not None
        assert len(result.bounding_boxes) >= 1

        for bbox in result.bounding_boxes:
            # page_width and page_height MUST be present
            assert "page_width" in bbox, (
                f"Missing page_width in bbox {bbox['id']}"
            )
            assert "page_height" in bbox, (
                f"Missing page_height in bbox {bbox['id']}"
            )
            assert bbox["page_width"] == pytest.approx(612.0, abs=1)
            assert bbox["page_height"] == pytest.approx(792.0, abs=1)

            # bbox coordinates must be within page bounds
            x0, y0, x1, y1 = bbox["bbox"]
            assert 0 <= x0 <= bbox["page_width"]
            assert 0 <= y0 <= bbox["page_height"]
            assert 0 <= x1 <= bbox["page_width"]
            assert 0 <= y1 <= bbox["page_height"]

    @pytest.mark.asyncio
    async def test_bboxes_normalizable_to_zero_one(self, tmp_path):
        """Simulates frontend normalization: all bboxes must produce 0-1 values."""
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")

        from docfold.engines.base import OutputFormat
        from docfold.engines.pymupdf_engine import PyMuPDFEngine

        pdf_path = str(tmp_path / "test.pdf")
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((50, 100), "Test content for normalization", fontsize=11)
        doc.save(pdf_path)
        doc.close()

        engine = PyMuPDFEngine()
        result = await engine.process(pdf_path, output_format=OutputFormat.MARKDOWN)

        assert result.bounding_boxes
        for bbox in result.bounding_boxes:
            pw = bbox["page_width"]
            ph = bbox["page_height"]
            x0, y0, x1, y1 = bbox["bbox"]
            # Normalize like the frontend does
            nx = x0 / pw
            ny = y0 / ph
            nw = (x1 - x0) / pw
            nh = (y1 - y0) / ph
            assert 0 <= nx <= 1, f"Normalized x={nx} out of range"
            assert 0 <= ny <= 1, f"Normalized y={ny} out of range"
            assert 0 < nw <= 1, f"Normalized width={nw} out of range"
            assert 0 < nh <= 1, f"Normalized height={nh} out of range"
            # No single block should cover > 95% of page
            assert nw < 0.95 or nh < 0.95, (
                f"Block covers entire page: w={nw:.2f} h={nh:.2f}"
            )


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
        assert caps.bounding_boxes is True
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


class TestDoclingServeEngine:
    def test_name(self):
        from docfold.engines.docling_serve_engine import DoclingServeEngine
        e = DoclingServeEngine()
        assert e.name == "docling_serve"

    def test_supported_extensions(self):
        from docfold.engines.docling_serve_engine import DoclingServeEngine
        e = DoclingServeEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "png" in exts
        assert "html" in exts

    def test_is_available_without_url(self):
        from docfold.engines.docling_serve_engine import DoclingServeEngine
        with patch.dict("os.environ", {}, clear=True):
            e = DoclingServeEngine(base_url="")
            assert e.is_available() is False

    def test_is_available_with_url(self):
        import types

        from docfold.engines.docling_serve_engine import DoclingServeEngine
        e = DoclingServeEngine(base_url="https://docling.example.com")
        with patch.dict("sys.modules", {"requests": types.ModuleType("requests")}):
            assert e.is_available() is True

    def test_config_stored(self):
        from docfold.engines.docling_serve_engine import DoclingServeEngine
        e = DoclingServeEngine(
            base_url="https://test.example.com",
            api_key="secret",
            do_ocr=False,
            timeout=120,
        )
        assert e._base_url == "https://test.example.com"
        assert e._api_key == "secret"
        assert e._do_ocr is False
        assert e._timeout == 120

    def test_capabilities(self):
        from docfold.engines.docling_serve_engine import DoclingServeEngine
        caps = DoclingServeEngine().capabilities
        assert isinstance(caps, EngineCapabilities)
        assert caps.images is True
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True

    @pytest.mark.asyncio
    async def test_process_html(self):
        pytest.importorskip("requests")
        from unittest.mock import MagicMock

        from docfold.engines.base import OutputFormat
        from docfold.engines.docling_serve_engine import DoclingServeEngine

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "document": {
                "html_content": "<p>OCR result</p>",
                "num_pages": 2,
            },
            "status": "success",
            "processing_time": 5.2,
        }

        e = DoclingServeEngine(base_url="https://test.example.com")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake")
            tmp_path = f.name

        try:
            with patch("requests.post", return_value=mock_response) as mock_post:
                result = await e.process(tmp_path, output_format=OutputFormat.HTML)

                assert result.content == "<p>OCR result</p>"
                assert result.engine_name == "docling_serve"
                assert result.format == OutputFormat.HTML
                assert result.pages == 2
                assert result.processing_time_ms > 0

                call_args = mock_post.call_args
                assert "/v1/convert/file" in call_args[0][0]
        finally:
            import os
            os.unlink(tmp_path)


class TestFirecrawlEngine:
    def test_name(self):
        from docfold.engines.firecrawl_engine import FirecrawlEngine
        e = FirecrawlEngine()
        assert e.name == "firecrawl"

    def test_supported_extensions(self):
        from docfold.engines.firecrawl_engine import FirecrawlEngine
        e = FirecrawlEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "html" in exts
        assert "htm" in exts
        assert "xml" in exts
        assert "docx" in exts
        assert "png" in exts
        assert "jpg" in exts

    def test_is_available_without_key(self):
        from docfold.engines.firecrawl_engine import FirecrawlEngine
        with patch.dict("os.environ", {}, clear=True):
            e = FirecrawlEngine(api_key=None)
            assert e.is_available() is False

    def test_is_available_with_key(self):
        from docfold.engines.firecrawl_engine import FirecrawlEngine
        e = FirecrawlEngine(api_key="fc-test-key")
        assert e.is_available() is True

    def test_config_stored(self):
        from docfold.engines.firecrawl_engine import FirecrawlEngine
        e = FirecrawlEngine(
            api_key="fc-key",
            api_url="https://custom.firecrawl.dev",
            timeout=60,
        )
        assert e._api_key == "fc-key"
        assert e._api_url == "https://custom.firecrawl.dev"
        assert e._timeout == 60

    def test_capabilities(self):
        from docfold.engines.firecrawl_engine import FirecrawlEngine
        caps = FirecrawlEngine().capabilities
        assert isinstance(caps, EngineCapabilities)
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.bounding_boxes is False
        assert caps.confidence is False
        assert caps.images is False

    @pytest.mark.asyncio
    async def test_process_pdf(self):
        """Firecrawl should handle PDF files via urllib POST."""
        import json
        from unittest.mock import MagicMock

        from docfold.engines.base import OutputFormat
        from docfold.engines.firecrawl_engine import FirecrawlEngine

        api_response = json.dumps({
            "success": True,
            "data": {
                "markdown": "# Invoice\n\nTotal: $100",
                "metadata": {"title": "Invoice"},
            },
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = api_response
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        e = FirecrawlEngine(api_key="fc-test")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake pdf content")
            tmp_path = f.name

        try:
            with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                result = await e.process(tmp_path, output_format=OutputFormat.MARKDOWN)

            assert result.content == "# Invoice\n\nTotal: $100"
            assert result.engine_name == "firecrawl"
            assert result.format == OutputFormat.MARKDOWN
            assert result.processing_time_ms >= 0

            # Verify the request was made with correct URL
            req = mock_urlopen.call_args[0][0]
            assert "/v1/scrape" in req.full_url
            body = json.loads(req.data)
            assert "rawContent" in body
        finally:
            import os
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_process_html(self):
        """Firecrawl should handle HTML files via urllib POST."""
        import json
        from unittest.mock import MagicMock

        from docfold.engines.base import OutputFormat
        from docfold.engines.firecrawl_engine import FirecrawlEngine

        api_response = json.dumps({
            "success": True,
            "data": {
                "markdown": "# Page Title\n\nSome content",
                "metadata": {"title": "Page Title"},
            },
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = api_response
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        e = FirecrawlEngine(api_key="fc-test")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<html><body><h1>Page Title</h1><p>Some content</p></body></html>")
            tmp_path = f.name

        try:
            with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
                result = await e.process(tmp_path, output_format=OutputFormat.MARKDOWN)

            assert result.content == "# Page Title\n\nSome content"
            assert result.engine_name == "firecrawl"

            # Verify HTML sent via "html" key, not rawContent
            req = mock_urlopen.call_args[0][0]
            body = json.loads(req.data)
            assert "html" in body
            assert "rawContent" not in body
        finally:
            import os
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_process_api_error(self):
        """Firecrawl should raise on API errors."""
        from urllib.error import HTTPError

        from docfold.engines.base import OutputFormat
        from docfold.engines.firecrawl_engine import FirecrawlEngine

        e = FirecrawlEngine(api_key="bad-key")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake")
            tmp_path = f.name

        try:
            with patch(
                "urllib.request.urlopen",
                side_effect=HTTPError(
                    url="https://api.firecrawl.dev/v1/scrape",
                    code=401, msg="Unauthorized", hdrs={}, fp=None,
                ),
            ):
                with pytest.raises(HTTPError):
                    await e.process(tmp_path, output_format=OutputFormat.MARKDOWN)
        finally:
            import os
            os.unlink(tmp_path)


class TestChandraEngine:
    def test_name(self):
        from docfold.engines.chandra_engine import ChandraEngine
        e = ChandraEngine()
        assert e.name == "chandra"

    def test_supported_extensions(self):
        from docfold.engines.chandra_engine import ChandraEngine
        e = ChandraEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "png" in exts
        assert "jpg" in exts
        assert "jpeg" in exts
        assert "tiff" in exts
        assert "bmp" in exts
        assert "webp" in exts

    def test_is_available_when_missing(self):
        from docfold.engines.chandra_engine import ChandraEngine
        e = ChandraEngine()
        with patch.dict("sys.modules", {"chandra": None}):
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.chandra_engine import ChandraEngine
        e = ChandraEngine(
            method="hf",
            model="datalab-to/chandra-ocr-2",
            prompt_type="ocr_with_layout",
            vllm_url="http://localhost:9000",
        )
        assert e._method == "hf"
        assert e._model == "datalab-to/chandra-ocr-2"
        assert e._prompt_type == "ocr_with_layout"
        assert e._vllm_url == "http://localhost:9000"

    def test_default_method_is_vllm(self):
        from docfold.engines.chandra_engine import ChandraEngine
        e = ChandraEngine()
        assert e._method == "vllm"

    def test_capabilities(self):
        from docfold.engines.chandra_engine import ChandraEngine
        caps = ChandraEngine().capabilities
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True
        assert caps.bounding_boxes is False
        assert caps.confidence is False


class TestUnlimitedOCREngine:
    def test_name(self):
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        e = UnlimitedOCREngine()
        assert e.name == "unlimited_ocr"

    def test_supported_extensions(self):
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        e = UnlimitedOCREngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "png" in exts
        assert "jpg" in exts
        assert "jpeg" in exts
        assert "tiff" in exts
        assert "bmp" in exts
        assert "webp" in exts

    def test_is_available_when_missing(self):
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        e = UnlimitedOCREngine()
        with patch.dict("sys.modules", {"torch": None}):
            result = e.is_available()
            assert isinstance(result, bool)

    def test_config_stored(self):
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        e = UnlimitedOCREngine(
            mode="base",
            model="baidu/Unlimited-OCR",
            max_length=16384,
            prompt="<image>parse.",
            device="cpu",
        )
        assert e._mode == "base"
        assert e._model == "baidu/Unlimited-OCR"
        assert e._max_length == 16384
        assert e._prompt == "<image>parse."
        assert e._device == "cpu"

    def test_default_mode_is_gundam(self):
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        e = UnlimitedOCREngine()
        assert e._mode == "gundam"

    def test_mode_params(self):
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        gundam = UnlimitedOCREngine(mode="gundam")._mode_params()
        assert gundam == (1024, 640, True)
        base = UnlimitedOCREngine(mode="base")._mode_params()
        assert base == (1024, 1024, False)

    def test_capabilities(self):
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        caps = UnlimitedOCREngine().capabilities
        assert caps.table_structure is True
        assert caps.heading_detection is True
        assert caps.reading_order is True
        assert caps.bounding_boxes is False
        assert caps.confidence is False

    @pytest.mark.asyncio
    async def test_process_returns_engine_result(self):
        """Unlimited-OCR processes an image and returns a valid EngineResult."""
        import os
        import tempfile
        from unittest.mock import MagicMock, patch

        from docfold.engines.base import EngineResult, OutputFormat
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine

        mock_model = MagicMock()
        mock_model.infer.return_value = "# Hello\n\nExtracted content"
        mock_tokenizer = MagicMock()

        prefix = "docfold.engines.unlimited_ocr_engine"
        with patch(
            f"{prefix}.UnlimitedOCREngine._ensure_model",
            return_value=(mock_model, mock_tokenizer),
        ):
            e = UnlimitedOCREngine(device="cpu")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(b"\x89PNG\r\n\x1a\n fake")
            try:
                result = await e.process(f.name, OutputFormat.MARKDOWN)
                assert isinstance(result, EngineResult)
                assert result.engine_name == "unlimited_ocr"
                assert result.content == "# Hello\n\nExtracted content"
                assert result.format == OutputFormat.MARKDOWN
                assert result.pages == 1
                assert result.processing_time_ms >= 0
                mock_model.infer.assert_called_once()
            finally:
                os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_process_json_output(self):
        """Unlimited-OCR returns per-page JSON when output_format is JSON."""
        import json
        import os
        import tempfile
        from unittest.mock import MagicMock, patch

        from docfold.engines.base import OutputFormat
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine

        mock_model = MagicMock()
        mock_model.infer.return_value = "page text"
        mock_tokenizer = MagicMock()

        prefix = "docfold.engines.unlimited_ocr_engine"
        with patch(
            f"{prefix}.UnlimitedOCREngine._ensure_model",
            return_value=(mock_model, mock_tokenizer),
        ):
            e = UnlimitedOCREngine(device="cpu")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(b"\x89PNG\r\n\x1a\n fake")
            try:
                result = await e.process(f.name, OutputFormat.JSON)
                assert result.format == OutputFormat.JSON
                parsed = json.loads(result.content)
                assert parsed["pages"][0]["text"] == "page text"
            finally:
                os.unlink(f.name)


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
        "docfold.engines.docling_serve_engine.DoclingServeEngine",
        "docfold.engines.firecrawl_engine.FirecrawlEngine",
        "docfold.engines.chandra_engine.ChandraEngine",
        "docfold.engines.marker_local_engine.MarkerLocalEngine",
        "docfold.engines.unlimited_ocr_engine.UnlimitedOCREngine",
    ])
    def test_has_required_attributes(self, engine_cls_path):
        module_path, cls_name = engine_cls_path.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, cls_name)
        _needs_key = {"MarkerEngine", "LlamaParseEngine", "MistralOCREngine", "FirecrawlEngine"}
        _needs_url = {"DoclingServeEngine"}
        if cls_name in _needs_key:
            engine = cls(api_key="test")
        elif cls_name in _needs_url:
            engine = cls(base_url="https://test.example.com")
        else:
            engine = cls()

        assert isinstance(engine.name, str)
        assert len(engine.name) > 0
        assert isinstance(engine.supported_extensions, set)
        assert len(engine.supported_extensions) > 0
        assert isinstance(engine.is_available(), bool)
        assert hasattr(engine, "process")
        assert callable(engine.process)
        assert isinstance(engine.capabilities, EngineCapabilities)

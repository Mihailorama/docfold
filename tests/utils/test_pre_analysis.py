"""Tests for pre-analysis utility."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from docfold.utils.pre_analysis import FileAnalysis, _analyze_sync, pre_analyze


class TestFileAnalysis:
    def test_dataclass_fields(self):
        fa = FileAnalysis(
            mime_type="application/pdf",
            extension="pdf",
            file_size_bytes=1024,
            category="pdf_text",
            page_count=5,
            has_text_layer=True,
            detected_language="en",
        )
        assert fa.mime_type == "application/pdf"
        assert fa.extension == "pdf"
        assert fa.file_size_bytes == 1024
        assert fa.category == "pdf_text"
        assert fa.page_count == 5
        assert fa.has_text_layer is True
        assert fa.detected_language == "en"

    def test_optional_fields_default_none(self):
        fa = FileAnalysis(
            mime_type="image/png",
            extension="png",
            file_size_bytes=512,
            category="image",
        )
        assert fa.page_count is None
        assert fa.has_text_layer is None
        assert fa.detected_language is None


class TestPreAnalyzeImages:
    def test_png_image(self, tmp_path):
        img_file = tmp_path / "scan.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = _analyze_sync(str(img_file))
        assert result.category == "image"
        assert result.extension == "png"
        assert result.mime_type == "image/png"
        assert result.page_count is None
        assert result.has_text_layer is None

    def test_jpg_image(self, tmp_path):
        img_file = tmp_path / "photo.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        result = _analyze_sync(str(img_file))
        assert result.category == "image"
        assert result.extension == "jpg"
        assert result.mime_type == "image/jpeg"

    def test_jpeg_image(self, tmp_path):
        img_file = tmp_path / "photo.jpeg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        result = _analyze_sync(str(img_file))
        assert result.category == "image"
        assert result.extension == "jpeg"

    def test_tiff_image(self, tmp_path):
        img_file = tmp_path / "scan.tiff"
        img_file.write_bytes(b"II*\x00" + b"\x00" * 100)

        result = _analyze_sync(str(img_file))
        assert result.category == "image"
        assert result.extension == "tiff"

    def test_bmp_image(self, tmp_path):
        img_file = tmp_path / "bitmap.bmp"
        img_file.write_bytes(b"BM" + b"\x00" * 100)

        result = _analyze_sync(str(img_file))
        assert result.category == "image"
        assert result.extension == "bmp"

    def test_webp_image(self, tmp_path):
        img_file = tmp_path / "photo.webp"
        img_file.write_bytes(b"RIFF" + b"\x00" * 100)

        result = _analyze_sync(str(img_file))
        assert result.category == "image"
        assert result.extension == "webp"


class TestPreAnalyzeOffice:
    def test_docx(self, tmp_path):
        f = tmp_path / "report.docx"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

        result = _analyze_sync(str(f))
        assert result.category == "office"
        assert result.extension == "docx"

    def test_xlsx(self, tmp_path):
        f = tmp_path / "data.xlsx"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

        result = _analyze_sync(str(f))
        assert result.category == "office"
        assert result.extension == "xlsx"

    def test_pptx(self, tmp_path):
        f = tmp_path / "slides.pptx"
        f.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

        result = _analyze_sync(str(f))
        assert result.category == "office"
        assert result.extension == "pptx"

    def test_csv(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3\n")

        result = _analyze_sync(str(f))
        assert result.category == "office"
        assert result.extension == "csv"


class TestPreAnalyzeHtml:
    def test_html(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<html><body>Hello</body></html>")

        result = _analyze_sync(str(f))
        assert result.category == "html"
        assert result.extension == "html"
        assert result.mime_type == "text/html"

    def test_htm(self, tmp_path):
        f = tmp_path / "page.htm"
        f.write_text("<html><body>Hello</body></html>")

        result = _analyze_sync(str(f))
        assert result.category == "html"
        assert result.extension == "htm"


class TestPreAnalyzeUnknown:
    def test_unknown_extension(self, tmp_path):
        f = tmp_path / "mystery.xyz"
        f.write_bytes(b"\x00" * 50)

        result = _analyze_sync(str(f))
        assert result.category == "unknown"
        assert result.extension == "xyz"
        assert result.mime_type == "application/octet-stream"

    def test_no_extension(self, tmp_path):
        f = tmp_path / "README"
        f.write_text("Hello world")

        result = _analyze_sync(str(f))
        assert result.category == "unknown"
        assert result.extension == ""


class TestPreAnalyzePdf:
    def test_text_pdf(self, tmp_path):
        """PDF with text layer → pdf_text."""
        # Create a mock pymupdf module
        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 200  # > 100 chars threshold

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 3
        mock_doc.__getitem__ = lambda self, i: mock_page
        mock_doc.close = MagicMock()

        pdf_file = tmp_path / "text.pdf"
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        with patch("docfold.utils.pre_analysis.pymupdf", create=True) as mock_pymupdf:
            # Patch the import inside the function
            import docfold.utils.pre_analysis as mod

            with patch.dict("sys.modules", {"pymupdf": mock_pymupdf}):
                mock_pymupdf.open.return_value = mock_doc
                result = mod._analyze_pdf(str(pdf_file), "pdf", "application/pdf", 108)

        assert result.category == "pdf_text"
        assert result.has_text_layer is True
        assert result.page_count == 3

    def test_scanned_pdf(self, tmp_path):
        """PDF without text layer → pdf_scanned."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "ab"  # ≤ 100 chars

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_doc.__getitem__ = lambda self, i: mock_page
        mock_doc.close = MagicMock()

        pdf_file = tmp_path / "scanned.pdf"
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        import docfold.utils.pre_analysis as mod

        with patch.dict("sys.modules", {"pymupdf": MagicMock()}) as modules:
            modules["pymupdf"].open.return_value = mock_doc
            result = mod._analyze_pdf(str(pdf_file), "pdf", "application/pdf", 108)

        assert result.category == "pdf_scanned"
        assert result.has_text_layer is False
        assert result.page_count == 1

    def test_pdf_without_pymupdf(self, tmp_path):
        """Without pymupdf installed, falls back to pdf_text category."""
        pdf_file = tmp_path / "fallback.pdf"
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        import docfold.utils.pre_analysis as mod

        # Simulate pymupdf not being available by patching the import to raise ImportError
        with patch.dict("sys.modules", {"pymupdf": None}):
            result = mod._analyze_pdf(str(pdf_file), "pdf", "application/pdf", 108)

        # Without pymupdf, we can't analyze → defaults
        assert result.category == "pdf_text"  # default
        assert result.page_count is None
        assert result.has_text_layer is None

    def test_file_size_reported(self, tmp_path):
        f = tmp_path / "test.png"
        f.write_bytes(b"\x89PNG" + b"\x00" * 500)

        result = _analyze_sync(str(f))
        assert result.file_size_bytes == 504  # 4 + 500

    def test_pdf_page_count(self, tmp_path):
        """Page count is correctly extracted from multi-page PDF."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 200

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 10
        mock_doc.__getitem__ = lambda self, i: mock_page
        mock_doc.close = MagicMock()

        pdf_file = tmp_path / "multipage.pdf"
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        import docfold.utils.pre_analysis as mod

        with patch.dict("sys.modules", {"pymupdf": MagicMock()}) as modules:
            modules["pymupdf"].open.return_value = mock_doc
            result = mod._analyze_pdf(str(pdf_file), "pdf", "application/pdf", 108)

        assert result.page_count == 10


class TestPreAnalyzeLanguageDetection:
    def test_without_langdetect(self, tmp_path):
        """Without langdetect installed, detected_language is None."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Hello world " * 50

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_doc.__getitem__ = lambda self, i: mock_page
        mock_doc.close = MagicMock()

        pdf_file = tmp_path / "english.pdf"
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        import docfold.utils.pre_analysis as mod

        with (
            patch.dict("sys.modules", {"pymupdf": MagicMock(), "langdetect": None}) as modules,
        ):
            modules["pymupdf"].open.return_value = mock_doc
            result = mod._analyze_pdf(str(pdf_file), "pdf", "application/pdf", 108)

        # langdetect not available → None
        assert result.detected_language is None


class TestPreAnalyzeAsync:
    async def test_async_wrapper(self, tmp_path):
        """pre_analyze() is an async wrapper that returns the same result."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG" + b"\x00" * 100)

        result = await pre_analyze(str(img_file))
        assert result.category == "image"
        assert result.extension == "png"
        assert isinstance(result, FileAnalysis)

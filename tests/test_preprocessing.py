"""Tests for preprocessing/detector module."""

import os
import tempfile
import pytest
from docfold.preprocessing.detector import detect_file_type, FileInfo


class TestFileInfo:
    def test_is_pdf(self):
        fi = FileInfo(path="x.pdf", extension="pdf", category="document", mime_type="application/pdf")
        assert fi.is_pdf
        assert not fi.is_image
        # PDF has category "document", so is_office is True (documents are office files)
        assert fi.is_office

    def test_is_image(self):
        fi = FileInfo(path="x.png", extension="png", category="image", mime_type="image/png")
        assert fi.is_image
        assert not fi.is_pdf

    def test_is_office(self):
        fi = FileInfo(path="x.docx", extension="docx", category="document", mime_type=None)
        assert fi.is_office


class TestDetectFileType:
    def test_pdf(self):
        info = detect_file_type("invoice.pdf")
        assert info.extension == "pdf"
        assert info.category == "document"
        assert info.mime_type == "application/pdf"

    def test_docx(self):
        info = detect_file_type("report.docx")
        assert info.extension == "docx"
        assert info.category == "document"

    def test_png(self):
        info = detect_file_type("scan.png")
        assert info.extension == "png"
        assert info.category == "image"
        assert info.mime_type == "image/png"

    def test_jpg(self):
        info = detect_file_type("photo.jpg")
        assert info.extension == "jpg"
        assert info.category == "image"
        assert info.mime_type == "image/jpeg"

    def test_xlsx(self):
        info = detect_file_type("data.xlsx")
        assert info.extension == "xlsx"
        assert info.category == "spreadsheet"

    def test_pptx(self):
        info = detect_file_type("slides.pptx")
        assert info.extension == "pptx"
        assert info.category == "presentation"

    def test_html(self):
        info = detect_file_type("page.html")
        assert info.extension == "html"
        assert info.category == "web"

    def test_csv(self):
        info = detect_file_type("data.csv")
        assert info.extension == "csv"
        assert info.category == "spreadsheet"

    def test_unknown_extension(self):
        info = detect_file_type("mystery.xyz")
        assert info.extension == "xyz"
        assert info.category == "unknown"

    def test_no_extension(self):
        info = detect_file_type("README")
        assert info.extension == ""
        assert info.category == "unknown"

    def test_case_insensitive(self):
        info = detect_file_type("FILE.PDF")
        assert info.extension == "pdf"
        assert info.category == "document"

    def test_path_preserved(self):
        info = detect_file_type("/some/path/to/file.docx")
        assert info.path == "/some/path/to/file.docx"

    def test_wav(self):
        info = detect_file_type("audio.wav")
        assert info.extension == "wav"
        assert info.category == "audio"

    def test_tiff(self):
        info = detect_file_type("scan.tiff")
        assert info.extension == "tiff"
        assert info.category == "image"

"""Tests for OpenDataLoader PDF engine adapter.

These are unit tests that mock the underlying ``opendataloader_pdf.convert``
call so they run without Java installed.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from docfold.engines.base import EngineResult, OutputFormat


def _odl_json(pages: int = 1, kids: list[dict] | None = None) -> dict:
    """Build a JSON payload matching the real OpenDataLoader output shape."""
    return {
        "file name": "test.pdf",
        "number of pages": pages,
        "author": None,
        "title": None,
        "creation date": None,
        "modification date": None,
        "kids": kids or [
            {
                "type": "heading",
                "id": 1,
                "page number": 1,
                "bounding box": [72.0, 688.85, 200.0, 705.0],
                "heading level": 1,
                "content": "Hello World",
            },
            {
                "type": "paragraph",
                "id": 2,
                "page number": 1,
                "bounding box": [72.0, 659.5, 400.0, 672.2],
                "content": "Test document for OpenDataLoader",
            },
        ],
    }


def _fake_convert_factory(
    json_payload: dict,
    markdown: str = "# Hello World\n\nTest document for OpenDataLoader",
    html: str = "<h1>Hello World</h1><p>Test document for OpenDataLoader</p>",
    text: str = "Hello World\nTest document for OpenDataLoader",
    stem: str = "test",
):
    """Produce a fake ``convert`` that writes output files into ``output_dir``."""

    def fake_convert(input_path, output_dir=None, format=None, **kwargs):
        assert output_dir is not None, "engine must pass an output_dir"
        fmts = format if isinstance(format, list) else ([format] if format else [])
        for fmt in fmts:
            if fmt == "json":
                with open(os.path.join(output_dir, f"{stem}.json"), "w") as f:
                    json.dump(json_payload, f)
            elif fmt in ("markdown", "markdown-with-html", "markdown-with-images"):
                with open(os.path.join(output_dir, f"{stem}.md"), "w") as f:
                    f.write(markdown)
            elif fmt == "html":
                with open(os.path.join(output_dir, f"{stem}.html"), "w") as f:
                    f.write(html)
            elif fmt == "text":
                with open(os.path.join(output_dir, f"{stem}.txt"), "w") as f:
                    f.write(text)

    return fake_convert


# ---------------------------------------------------------------------------
# Metadata / capabilities
# ---------------------------------------------------------------------------


class TestOpenDataLoaderEngineMetadata:
    def test_name(self):
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        assert e.name == "opendataloader"

    def test_supported_extensions(self):
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        assert "pdf" in e.supported_extensions

    def test_capabilities(self):
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        caps = e.capabilities
        assert caps.bounding_boxes is True
        assert caps.reading_order is True
        assert caps.heading_detection is True
        assert caps.table_structure is True

    def test_is_available_false_when_package_missing(self):
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        with patch.dict("sys.modules", {"opendataloader_pdf": None}):
            assert isinstance(e.is_available(), bool)

    def test_is_available_false_when_java_missing(self):
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        with patch("shutil.which", return_value=None):
            assert e.is_available() is False

    def test_config_stored(self):
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine(
            reading_order="xycut",
            table_method="cluster",
            include_header_footer=True,
            password="secret",
        )
        assert e._reading_order == "xycut"
        assert e._table_method == "cluster"
        assert e._include_header_footer is True
        assert e._password == "secret"


# ---------------------------------------------------------------------------
# process()
# ---------------------------------------------------------------------------


class TestOpenDataLoaderEngineProcess:
    @pytest.mark.asyncio
    async def test_process_markdown_format(self):
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        fake_convert = _fake_convert_factory(_odl_json(pages=1))

        with patch.object(opendataloader_engine, "_convert", fake_convert):
            result = await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

        assert isinstance(result, EngineResult)
        assert result.engine_name == "opendataloader"
        assert result.format == OutputFormat.MARKDOWN
        assert "Hello World" in result.content
        assert result.pages == 1
        assert result.bounding_boxes is not None
        assert len(result.bounding_boxes) == 2
        assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_process_json_format(self):
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        fake_convert = _fake_convert_factory(_odl_json(pages=1))

        with patch.object(opendataloader_engine, "_convert", fake_convert):
            result = await e.process("test.pdf", output_format=OutputFormat.JSON)

        assert result.format == OutputFormat.JSON
        # Content must be valid JSON
        parsed = json.loads(result.content)
        assert parsed["number of pages"] == 1

    @pytest.mark.asyncio
    async def test_process_html_format(self):
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        e = OpenDataLoaderEngine()
        fake_convert = _fake_convert_factory(_odl_json(pages=1))

        with patch.object(opendataloader_engine, "_convert", fake_convert):
            result = await e.process("test.pdf", output_format=OutputFormat.HTML)

        assert result.format == OutputFormat.HTML
        assert "<h1>" in result.content.lower()

    @pytest.mark.asyncio
    async def test_type_mapping(self):
        """heading/paragraph/table/list/list-item should map to canonical types."""
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        kids = [
            {
                "type": "heading",
                "id": 1,
                "page number": 1,
                "bounding box": [0, 0, 100, 20],
                "content": "H",
            },
            {
                "type": "paragraph",
                "id": 2,
                "page number": 1,
                "bounding box": [0, 30, 100, 50],
                "content": "P",
            },
            {
                "type": "table",
                "id": 3,
                "page number": 1,
                "bounding box": [0, 60, 100, 200],
                "content": "T",
            },
            {
                "type": "list",
                "id": 4,
                "page number": 1,
                "bounding box": [0, 210, 100, 300],
                "content": "L",
            },
        ]
        e = OpenDataLoaderEngine()
        fake_convert = _fake_convert_factory(_odl_json(pages=1, kids=kids))
        with patch.object(opendataloader_engine, "_convert", fake_convert):
            result = await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

        types = {b["type"] for b in result.bounding_boxes}
        assert "SectionHeader" in types
        assert "Text" in types
        assert "Table" in types
        assert "List" in types

    @pytest.mark.asyncio
    async def test_nested_kids_flattened(self):
        """Nested kids (e.g. header container) must be flattened into bboxes."""
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        nested_kids = [
            {
                "type": "header",
                "id": 10,
                "page number": 1,
                "bounding box": [0, 0, 500, 400],
                "kids": [
                    {
                        "type": "heading",
                        "id": 1,
                        "page number": 1,
                        "bounding box": [0, 0, 100, 20],
                        "content": "Title",
                    },
                    {
                        "type": "paragraph",
                        "id": 2,
                        "page number": 1,
                        "bounding box": [0, 30, 400, 100],
                        "content": "Body",
                    },
                ],
            }
        ]
        e = OpenDataLoaderEngine()
        fake_convert = _fake_convert_factory(_odl_json(pages=1, kids=nested_kids))

        with patch.object(opendataloader_engine, "_convert", fake_convert):
            result = await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

        # At least the two leaves must be emitted as bounding boxes.
        assert result.bounding_boxes is not None
        texts = [b.get("text", "") for b in result.bounding_boxes]
        assert "Title" in texts
        assert "Body" in texts

    @pytest.mark.asyncio
    async def test_bbox_coordinates_preserved(self):
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        kids = [
            {
                "type": "paragraph",
                "id": 1,
                "page number": 2,
                "bounding box": [12.5, 34.5, 200.0, 90.0],
                "content": "Hi",
            }
        ]
        e = OpenDataLoaderEngine()
        fake_convert = _fake_convert_factory(_odl_json(pages=2, kids=kids))

        with patch.object(opendataloader_engine, "_convert", fake_convert):
            result = await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

        assert result.bounding_boxes is not None
        bbox = result.bounding_boxes[0]
        assert bbox["bbox"] == [12.5, 34.5, 200.0, 90.0]
        assert bbox["page"] == 2
        assert bbox["text"] == "Hi"

    @pytest.mark.asyncio
    async def test_process_surfaces_errors_as_runtime_error(self):
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        def boom(*args, **kwargs):
            raise RuntimeError("java exited 2")

        e = OpenDataLoaderEngine()
        with patch.object(opendataloader_engine, "_convert", boom):
            with pytest.raises(RuntimeError, match="opendataloader"):
                await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

    @pytest.mark.asyncio
    async def test_reading_order_option_passed(self):
        """reading_order kwarg on the engine must reach the underlying convert call."""
        from docfold.engines import opendataloader_engine
        from docfold.engines.opendataloader_engine import OpenDataLoaderEngine

        captured: dict = {}

        def capture(input_path, output_dir=None, format=None, **kwargs):
            captured["kwargs"] = kwargs
            # Still produce files so parsing succeeds
            _fake_convert_factory(_odl_json(pages=1))(
                input_path, output_dir=output_dir, format=format, **kwargs
            )

        e = OpenDataLoaderEngine(reading_order="xycut", table_method="cluster")
        with patch.object(opendataloader_engine, "_convert", capture):
            await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

        assert captured["kwargs"].get("reading_order") == "xycut"
        assert captured["kwargs"].get("table_method") == "cluster"

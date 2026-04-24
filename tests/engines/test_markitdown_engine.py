"""Tests for the MarkItDown engine adapter.

The ``markitdown`` package is not a test-time dependency; these tests mock the
import path and the ``MarkItDown`` class so they run on any host.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from docfold.engines.base import EngineResult, OutputFormat


def _install_fake_markitdown(text_content: str = "# Hello\n\nWorld") -> MagicMock:
    """Inject a fake ``markitdown`` module into ``sys.modules``.

    Returns the mock ``MarkItDown`` class so individual tests can assert
    on how it was called.
    """
    fake_module = types.ModuleType("markitdown")
    mock_class = MagicMock(name="MarkItDown")

    # Default: MarkItDown().convert(path).text_content = text_content
    instance = MagicMock()
    convert_result = MagicMock()
    convert_result.text_content = text_content
    convert_result.title = None
    instance.convert.return_value = convert_result
    mock_class.return_value = instance

    fake_module.MarkItDown = mock_class
    sys.modules["markitdown"] = fake_module
    return mock_class


def _remove_fake_markitdown() -> None:
    sys.modules.pop("markitdown", None)


@pytest.fixture
def fake_markitdown():
    mock_class = _install_fake_markitdown()
    try:
        yield mock_class
    finally:
        _remove_fake_markitdown()


class TestMarkItDownEngineMetadata:
    def test_name(self):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        assert MarkItDownEngine().name == "markitdown"

    def test_supported_extensions_covers_markitdown_formats(self):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        exts = MarkItDownEngine().supported_extensions
        # The formats markitdown documents support: Office, PDFs, images,
        # web/markup, tabular, ePub, audio.
        for fmt in ("pdf", "docx", "pptx", "xlsx", "html", "htm",
                    "png", "jpg", "jpeg", "csv", "json", "xml", "epub"):
            assert fmt in exts, f"expected '{fmt}' in supported_extensions"

    def test_capabilities_are_empty_by_default(self):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        caps = MarkItDownEngine().capabilities
        # markitdown returns plain markdown with no layout info
        assert caps.bounding_boxes is False
        assert caps.confidence is False
        assert caps.table_structure is False

    def test_is_available_true_when_importable(self, fake_markitdown):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        assert MarkItDownEngine().is_available() is True

    def test_is_available_false_when_missing(self):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        _remove_fake_markitdown()
        with patch.dict(sys.modules, {"markitdown": None}):
            assert MarkItDownEngine().is_available() is False


class TestMarkItDownEngineProcess:
    @pytest.mark.asyncio
    async def test_process_markdown_returns_engine_result(self, fake_markitdown):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        # Custom markdown payload for this test
        instance = fake_markitdown.return_value
        instance.convert.return_value.text_content = (
            "# Invoice 2024\n\nAmount: **$1,250.00**"
        )

        engine = MarkItDownEngine()
        result = await engine.process("invoice.pdf", output_format=OutputFormat.MARKDOWN)

        assert isinstance(result, EngineResult)
        assert result.engine_name == "markitdown"
        assert result.format == OutputFormat.MARKDOWN
        assert "Invoice 2024" in result.content
        assert "$1,250.00" in result.content
        assert result.processing_time_ms >= 0

        # MarkItDown().convert("invoice.pdf") must have been called
        instance.convert.assert_called_once()
        call_args = instance.convert.call_args
        assert call_args.args[0] == "invoice.pdf"

    @pytest.mark.asyncio
    async def test_process_runs_convert_in_executor(self, fake_markitdown):
        """The sync convert() call must be dispatched through run_in_executor
        so it does not block the event loop."""
        import asyncio

        from docfold.engines.markitdown_engine import MarkItDownEngine

        engine = MarkItDownEngine()

        loop = asyncio.get_running_loop()
        original_run_in_executor = loop.run_in_executor
        call_count = {"n": 0}

        async def spy(*args, **kwargs):
            call_count["n"] += 1
            return await original_run_in_executor(*args, **kwargs)

        with patch.object(loop, "run_in_executor", side_effect=spy):
            await engine.process("some.pdf", output_format=OutputFormat.MARKDOWN)

        assert call_count["n"] >= 1, "convert() must be dispatched via run_in_executor"

    @pytest.mark.asyncio
    async def test_process_text_format_returns_plain_markdown(self, fake_markitdown):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        instance = fake_markitdown.return_value
        instance.convert.return_value.text_content = "# Title\n\nBody"

        result = await MarkItDownEngine().process("x.pdf", output_format=OutputFormat.TEXT)

        assert result.format == OutputFormat.TEXT
        # TEXT format should pass the markdown string through unchanged.
        assert "Title" in result.content
        assert "Body" in result.content

    @pytest.mark.asyncio
    async def test_process_json_format_wraps_markdown(self, fake_markitdown):
        import json as _json

        from docfold.engines.markitdown_engine import MarkItDownEngine

        instance = fake_markitdown.return_value
        instance.convert.return_value.text_content = "# Doc\n\nHello"

        result = await MarkItDownEngine().process("x.pdf", output_format=OutputFormat.JSON)

        assert result.format == OutputFormat.JSON
        parsed = _json.loads(result.content)
        assert isinstance(parsed, dict)
        assert "markdown" in parsed
        assert "Doc" in parsed["markdown"]

    @pytest.mark.asyncio
    async def test_process_html_format_wraps_markdown(self, fake_markitdown):
        from docfold.engines.markitdown_engine import MarkItDownEngine

        instance = fake_markitdown.return_value
        instance.convert.return_value.text_content = "# Doc"

        result = await MarkItDownEngine().process("x.pdf", output_format=OutputFormat.HTML)

        assert result.format == OutputFormat.HTML
        # Markdown text must be preserved inside the HTML wrapper.
        assert "Doc" in result.content
        assert result.content.strip().startswith("<")

    @pytest.mark.asyncio
    async def test_process_missing_dependency_raises(self):
        """When markitdown isn't installed, process() must raise a clear error."""
        from docfold.engines.markitdown_engine import MarkItDownEngine

        _remove_fake_markitdown()
        with patch.dict(sys.modules, {"markitdown": None}):
            engine = MarkItDownEngine()
            with pytest.raises((RuntimeError, ImportError, ModuleNotFoundError)):
                await engine.process("any.pdf", output_format=OutputFormat.MARKDOWN)

    @pytest.mark.asyncio
    async def test_process_preserves_unicode(self, fake_markitdown):
        """Non-ASCII text (Arabic, CJK, Hebrew) must pass through unchanged."""
        from docfold.engines.markitdown_engine import MarkItDownEngine

        payload = "تقرير سنوي 2024\n\n2024年度报告\n\nדוח שנתי 2024"
        instance = fake_markitdown.return_value
        instance.convert.return_value.text_content = payload

        result = await MarkItDownEngine().process("i18n.pdf", output_format=OutputFormat.MARKDOWN)

        assert "تقرير" in result.content
        assert "年度报告" in result.content
        assert "דוח" in result.content

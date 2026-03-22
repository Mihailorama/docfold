"""Tests for LiteParse engine adapter — CLI-based local document parser."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docfold.engines.base import EngineResult, OutputFormat


def _make_liteparse_json(pages: list[dict]) -> str:
    """Build a JSON string matching the real LiteParse CLI output format."""
    return json.dumps({"pages": pages})


def _simple_page(
    page: int = 1,
    text: str = "Hello",
    text_items: list[dict] | None = None,
    width: int = 612,
    height: int = 792,
) -> dict:
    """Build a single page in LiteParse JSON format."""
    if text_items is None:
        text_items = [
            {"text": text, "x": 72, "y": 100, "width": 50, "height": 14},
        ]
    return {
        "page": page,
        "width": width,
        "height": height,
        "text": text,
        "textItems": text_items,
        "boundingBoxes": [],
    }


class TestLiteParseEngineMetadata:
    def test_name(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()
        assert e.name == "liteparse"

    def test_supported_extensions(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()
        exts = e.supported_extensions
        assert "pdf" in exts
        assert "docx" in exts
        assert "pptx" in exts
        assert "xlsx" in exts
        assert "png" in exts
        assert "jpg" in exts

    def test_capabilities(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()
        caps = e.capabilities
        assert caps.bounding_boxes is True
        assert caps.confidence is True

    def test_is_available_when_lit_exists(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()
        with patch("shutil.which", return_value="/usr/local/bin/lit"):
            assert e.is_available() is True

    def test_is_available_when_lit_missing(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()
        with patch("shutil.which", return_value=None):
            assert e.is_available() is False

    def test_custom_cli_path(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine(cli_path="/opt/bin/lit")
        assert e._cli_path == "/opt/bin/lit"

    def test_config_stored(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine(ocr_enabled=False, ocr_language="fra", dpi=300)
        assert e._ocr_enabled is False
        assert e._ocr_language == "fra"
        assert e._dpi == 300


class TestLiteParseEngineProcess:
    @pytest.mark.asyncio
    async def test_process_text_format(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.communicate = AsyncMock(
            return_value=(b"Hello world\nThis is a test document.", b"")
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            result = await e.process("test.pdf", output_format=OutputFormat.TEXT)

            assert isinstance(result, EngineResult)
            assert result.engine_name == "liteparse"
            assert "Hello world" in result.content
            assert result.format == OutputFormat.TEXT
            assert result.processing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_process_markdown_format(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()

        json_output = _make_liteparse_json([
            {
                "page": 1,
                "width": 612,
                "height": 792,
                "text": "# Title\n\nSome paragraph text.",
                "textItems": [
                    {"text": "Title", "x": 10, "y": 20, "width": 190, "height": 30},
                    {"text": "Some paragraph text.", "x": 10, "y": 60, "width": 390, "height": 30},
                ],
                "boundingBoxes": [],
            }
        ])

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.communicate = AsyncMock(
            return_value=(json_output.encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            result = await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

            assert isinstance(result, EngineResult)
            assert result.engine_name == "liteparse"
            assert result.format == OutputFormat.MARKDOWN
            assert result.bounding_boxes is not None
            assert len(result.bounding_boxes) == 2
            assert result.pages == 1

    @pytest.mark.asyncio
    async def test_process_json_format(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()

        json_output = _make_liteparse_json([_simple_page(text="Test content")])

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.communicate = AsyncMock(
            return_value=(json_output.encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            result = await e.process("test.pdf", output_format=OutputFormat.JSON)

            assert result.format == OutputFormat.JSON
            parsed = json.loads(result.content)
            assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_process_failure_raises(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.communicate = AsyncMock(
            return_value=(b"", b"Error: file not found")
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            with pytest.raises(RuntimeError, match="liteparse"):
                await e.process("missing.pdf")

    @pytest.mark.asyncio
    async def test_ocr_disabled_flag(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine(ocr_enabled=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.communicate = AsyncMock(return_value=(b"text", b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            await e.process("test.pdf", output_format=OutputFormat.TEXT)

            call_args = mock_exec.call_args
            assert "--no-ocr" in call_args[0]

    @pytest.mark.asyncio
    async def test_custom_dpi_passed(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine(dpi=300)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.communicate = AsyncMock(return_value=(b"text", b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            await e.process("test.pdf", output_format=OutputFormat.TEXT)

            call_args = mock_exec.call_args
            assert "--dpi" in call_args[0]
            assert "300" in call_args[0]

    @pytest.mark.asyncio
    async def test_bounding_boxes_from_text_items(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()

        json_output = _make_liteparse_json([
            {
                "page": 1,
                "width": 612,
                "height": 792,
                "text": "Hello",
                "textItems": [
                    {
                        "text": "Hello",
                        "x": 10.0,
                        "y": 20.0,
                        "width": 90.0,
                        "height": 20.0,
                    }
                ],
                "boundingBoxes": [],
            }
        ])

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.communicate = AsyncMock(
            return_value=(json_output.encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            result = await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

            assert result.bounding_boxes is not None
            bbox = result.bounding_boxes[0]
            # bbox should be [x, y, x+width, y+height]
            assert bbox["bbox"] == [10.0, 20.0, 100.0, 40.0]
            assert bbox["text"] == "Hello"
            assert bbox["page"] == 1
            assert bbox["page_width"] == 612
            assert bbox["page_height"] == 792

    @pytest.mark.asyncio
    async def test_extract_json_with_log_prefix(self):
        """LiteParse CLI may output log lines before JSON."""
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()

        raw_json = _make_liteparse_json([_simple_page(text="Test")])
        # Simulate log lines before JSON
        prefixed = f"Processing file: test.pdf\nLoaded PDF with 1 pages\n{raw_json}"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.communicate = AsyncMock(
            return_value=(prefixed.encode(), b"")
        )

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result

            result = await e.process("test.pdf", output_format=OutputFormat.MARKDOWN)

            assert result.content == "Test"
            assert result.pages == 1

"""Tests for LiteParse engine adapter — CLI-based local document parser."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docfold.engines.base import EngineResult, OutputFormat


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
        mock_result.stdout = "Hello world\nThis is a test document."
        mock_result.stderr = ""

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            mock_result.communicate = AsyncMock(
                return_value=(mock_result.stdout.encode(), b"")
            )

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

        json_output = json.dumps({
            "pages": [
                {
                    "page": 1,
                    "content": {
                        "text": "# Title\n\nSome paragraph text.",
                        "items": [
                            {
                                "text": "Title",
                                "bbox": [10, 20, 200, 50],
                                "confidence": 0.98,
                            },
                            {
                                "text": "Some paragraph text.",
                                "bbox": [10, 60, 400, 90],
                                "confidence": 0.95,
                            },
                        ],
                    },
                    "width": 612,
                    "height": 792,
                }
            ]
        })

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

        json_output = json.dumps({
            "pages": [
                {
                    "page": 1,
                    "content": {
                        "text": "Test content",
                        "items": [],
                    },
                    "width": 612,
                    "height": 792,
                }
            ]
        })

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

            # Verify --no-ocr flag is passed
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
    async def test_bounding_boxes_extraction(self):
        from docfold.engines.liteparse_engine import LiteParseEngine

        e = LiteParseEngine()

        json_output = json.dumps({
            "pages": [
                {
                    "page": 1,
                    "content": {
                        "text": "Hello",
                        "items": [
                            {
                                "text": "Hello",
                                "bbox": [10.0, 20.0, 100.0, 40.0],
                                "confidence": 0.97,
                            }
                        ],
                    },
                    "width": 612,
                    "height": 792,
                }
            ]
        })

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
            assert bbox["bbox"] == [10.0, 20.0, 100.0, 40.0]
            assert bbox["text"] == "Hello"
            assert bbox["page"] == 1
            assert bbox["page_width"] == 612
            assert bbox["page_height"] == 792

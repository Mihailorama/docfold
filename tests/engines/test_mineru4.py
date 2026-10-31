"""MinerU 4.x path (``mineru.parse``; VLM model MinerU2.5-Pro)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.mineru_engine import MinerUEngine


def _result(md="# Hi", pages=2):
    r = MagicMock()
    r.markdown.return_value = md
    r.structured_content.return_value = {"blocks": ["x"]}
    r.pages = [object()] * pages
    return r


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4")
    return str(p)


@pytest.mark.asyncio
async def test_uses_mineru4_parse_when_available(pdf):
    parse = MagicMock(return_value=_result())
    vlm = MagicMock(side_effect=lambda **kw: SimpleNamespace(**kw))
    with patch("docfold.engines.mineru_engine._load_mineru4", return_value=(parse, vlm)):
        e = MinerUEngine(parse_method="ocr", tier="advanced",
                         server_url="http://gpu:30000/v1", vlm_model="m")
        result = await e.process(pdf, start_page=1, end_page=3)
    assert result.content == "# Hi"
    assert result.pages == 2
    kwargs = parse.call_args.kwargs
    assert parse.call_args.args == (pdf,)
    assert kwargs["tier"] == "advanced"
    assert kwargs["ocr_mode"] == "ocr"
    assert kwargs["page_range"] == "2-4"
    assert kwargs["vlm_config"].server_url == "http://gpu:30000/v1"
    assert kwargs["vlm_config"].model == "m"
    assert result.metadata["tier"] == "advanced"


@pytest.mark.asyncio
async def test_mineru4_json_and_defaults(pdf):
    parse = MagicMock(return_value=_result())
    with patch("docfold.engines.mineru_engine._load_mineru4", return_value=(parse, MagicMock())):
        result = await MinerUEngine().process(pdf, OutputFormat.JSON)
    assert json.loads(result.content) == {"blocks": ["x"]}
    kwargs = parse.call_args.kwargs
    assert kwargs["tier"] == "standard"
    assert kwargs["ocr_mode"] == "auto"
    assert kwargs["page_range"] == ""
    assert kwargs["vlm_config"] is None


def test_page_range():
    from docfold.engines.mineru_engine import _page_range
    assert _page_range(None, None) == ""
    assert _page_range(0, None) == ""
    assert _page_range(4, None) == "5-r1"
    assert _page_range(None, 2) == "1-3"

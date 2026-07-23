"""Tests for the docfold MCP server (docfold-mcp)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from docfold import mcp_server
from docfold.engines.base import EngineResult, OutputFormat

requires_mcp = pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None,
    reason="mcp extra not installed (pip install 'docfold[mcp]')",
)


class StubRouter:
    """Minimal EngineRouter stand-in for tool tests."""

    def __init__(self, result: EngineResult | None = None, exc: Exception | None = None):
        self.result = result
        self.exc = exc
        self.calls: list[dict[str, Any]] = []

    async def process(self, file_path: str, output_format=OutputFormat.MARKDOWN, **kwargs):
        self.calls.append({"file_path": file_path, "output_format": output_format, **kwargs})
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result

    def list_engines(self) -> list[dict[str, Any]]:
        return [
            {"name": "pymupdf", "available": True, "extensions": ["pdf"], "capabilities": {}},
            {"name": "docling", "available": False, "extensions": ["pdf"], "capabilities": {}},
        ]


def _result(**overrides: Any) -> EngineResult:
    defaults: dict[str, Any] = dict(
        content="# hello",
        format=OutputFormat.MARKDOWN,
        engine_name="stub",
        pages=1,
        processing_time_ms=5,
    )
    defaults.update(overrides)
    return EngineResult(**defaults)


# ---------------------------------------------------------------------------
# 1. main() exits 2 with an install hint when the mcp extra is missing
# ---------------------------------------------------------------------------


def test_main_exits_with_install_hint_when_mcp_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise() -> Any:
        raise ImportError("No module named 'mcp'")

    monkeypatch.setattr(mcp_server, "build_server", _raise)

    with pytest.raises(SystemExit) as excinfo:
        mcp_server.main()

    assert excinfo.value.code == 2
    assert 'pip install "docfold[mcp]"' in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 2. _result_payload drops bulky slots, keeps the useful ones
# ---------------------------------------------------------------------------


def test_result_payload_drops_images_and_bounding_boxes() -> None:
    result = _result(
        images={"page1.png": "aGVsbG8="},
        bounding_boxes=[{"type": "Text", "bbox": [0, 0, 1, 1], "page": 1}],
        tables=[{"col": "val"}],
    )
    payload = mcp_server._result_payload(result)
    assert "images" not in payload
    assert "bounding_boxes" not in payload
    assert payload["content"] == "# hello"
    assert payload["format"] == "markdown"
    assert payload["engine"] == "stub"
    assert payload["tables"] == [{"col": "val"}]


# ---------------------------------------------------------------------------
# 3. build_server registers exactly the four documented tools
# ---------------------------------------------------------------------------


@requires_mcp
async def test_build_server_registers_four_tools() -> None:
    server = mcp_server.build_server()
    tools = await server.list_tools()
    assert {t.name for t in tools} == {
        "parse_document",
        "extract_tables",
        "list_engines",
        "classify_document",
    }


# ---------------------------------------------------------------------------
# 4. parse_document → payload, engine/format forwarded
# ---------------------------------------------------------------------------


@requires_mcp
async def test_parse_document_returns_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-1.4")
    router = StubRouter(result=_result())
    monkeypatch.setattr(mcp_server, "_get_router", lambda: router)

    server = mcp_server.build_server()
    _content, structured = await server.call_tool(
        "parse_document",
        {"path_or_url": str(doc), "engine": "pymupdf", "output_format": "text"},
    )

    assert router.calls[0]["file_path"] == str(doc)
    assert router.calls[0]["engine_hint"] == "pymupdf"
    assert router.calls[0]["output_format"] == OutputFormat.TEXT
    assert structured["content"] == "# hello"
    assert structured["engine"] == "stub"


# ---------------------------------------------------------------------------
# 5. parse_document with a URL downloads to a local file first
# ---------------------------------------------------------------------------


@requires_mcp
async def test_parse_document_url_is_downloaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    local = tmp_path / "remote.pdf"
    local.write_bytes(b"%PDF-1.4")
    fetched: list[str] = []

    def _fake_fetch(url: str) -> Path:
        fetched.append(url)
        return local

    router = StubRouter(result=_result())
    monkeypatch.setattr(mcp_server, "_get_router", lambda: router)
    monkeypatch.setattr(mcp_server, "_fetch_url", _fake_fetch)

    server = mcp_server.build_server()
    _content, structured = await server.call_tool(
        "parse_document", {"path_or_url": "https://example.com/remote.pdf"}
    )

    assert fetched == ["https://example.com/remote.pdf"]
    assert router.calls[0]["file_path"] == str(local)
    assert structured["content"] == "# hello"


# ---------------------------------------------------------------------------
# 6. Failures are structured — never garbage-as-content
# ---------------------------------------------------------------------------


@requires_mcp
async def test_parse_document_all_engines_failed_structured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-1.4")
    exc = RuntimeError(
        "All engines failed for 'doc.pdf'. Errors: pymupdf: boom; docling: bang"
    )
    monkeypatch.setattr(mcp_server, "_get_router", lambda: StubRouter(exc=exc))

    server = mcp_server.build_server()
    _content, structured = await server.call_tool(
        "parse_document", {"path_or_url": str(doc)}
    )

    assert structured["error"] == "all engines failed"
    assert structured["failures"] == ["pymupdf: boom", "docling: bang"]
    assert "content" not in structured


@requires_mcp
async def test_parse_document_missing_file_structured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = mcp_server.build_server()
    _content, structured = await server.call_tool(
        "parse_document", {"path_or_url": "/nonexistent/nope.pdf"}
    )
    assert "error" in structured
    assert isinstance(structured["failures"], list)
    assert "content" not in structured


# ---------------------------------------------------------------------------
# 7. extract_tables
# ---------------------------------------------------------------------------


@requires_mcp
async def test_extract_tables_returns_tables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-1.4")
    tables = [{"a": 1}, {"a": 2}]
    router = StubRouter(result=_result(tables=tables))
    monkeypatch.setattr(mcp_server, "_get_router", lambda: router)

    server = mcp_server.build_server()
    _content, structured = await server.call_tool("extract_tables", {"path_or_url": str(doc)})

    assert structured["tables"] == tables
    assert structured["engine"] == "stub"


@requires_mcp
async def test_extract_tables_none_becomes_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = tmp_path / "doc.pdf"
    doc.write_bytes(b"%PDF-1.4")
    router = StubRouter(result=_result(tables=None))
    monkeypatch.setattr(mcp_server, "_get_router", lambda: router)

    server = mcp_server.build_server()
    _content, structured = await server.call_tool("extract_tables", {"path_or_url": str(doc)})

    assert structured["tables"] == []


# ---------------------------------------------------------------------------
# 8. list_engines / classify_document
# ---------------------------------------------------------------------------


@requires_mcp
async def test_list_engines_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "_get_router", lambda: StubRouter())
    server = mcp_server.build_server()
    _content, structured = await server.call_tool("list_engines", {})
    engines = structured["engines"]
    assert {e["name"] for e in engines} == {"pymupdf", "docling"}
    assert all(set(e) == {"name", "available", "extensions"} for e in engines)


@requires_mcp
async def test_classify_document_tool(tmp_path: Path) -> None:
    doc = tmp_path / "photo.png"
    doc.write_bytes(b"\x89PNG\r\n")
    server = mcp_server.build_server()
    _content, structured = await server.call_tool("classify_document", {"path": str(doc)})
    assert structured["category"] == "image"


# ---------------------------------------------------------------------------
# 9. Token budget — tool definitions stay tight
# ---------------------------------------------------------------------------

_TOKEN_BUDGET = 1000
"""Rough-estimate token ceiling (chars/4) for all tool defs + instructions.

If this fails, a tool description got bloated — trim it rather than raising
the budget."""


@requires_mcp
async def test_tool_definitions_within_token_budget() -> None:
    import json as _json

    server = mcp_server.build_server()
    tools = await server.list_tools()
    blob = _json.dumps([t.model_dump(exclude_none=True) for t in tools]) + mcp_server._INSTRUCTIONS
    estimated_tokens = len(blob) // 4
    assert estimated_tokens <= _TOKEN_BUDGET, (
        f"tool definitions estimate {estimated_tokens} tokens > budget {_TOKEN_BUDGET}"
    )

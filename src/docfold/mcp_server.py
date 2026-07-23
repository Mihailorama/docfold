"""docfold MCP server entry point.

Exposes docfold to MCP clients (Claude Code, Claude Desktop, Cursor, Codex,
VS Code, …) over stdio. Requires the ``mcp`` optional extra:

    pip install "docfold[mcp]"

One-click registration into a client: ``docfold install claude`` (see
``docfold install --help`` for other clients).

Tools:
    - parse_document     — file/URL → structured markdown/html/json/text
    - extract_tables     — file/URL → extracted tables
    - list_engines       — registered engines + availability
    - classify_document  — routing category (pdf_text, pdf_scanned, office, …)
"""

from __future__ import annotations

import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

    from docfold.engines.base import EngineResult
    from docfold.engines.router import EngineRouter

_INSTALL_HINT = (
    'docfold-mcp requires the "mcp" optional extra:\n\n    pip install "docfold[mcp]"\n'
)

_INSTRUCTIONS = (
    "docfold turns documents (PDF, DOCX, XLSX, HTML, images, …) into "
    "structured, LLM-ready output through one interface over 20+ parsing "
    "engines. Use parse_document for a file or URL, extract_tables for "
    "tabular data, list_engines to see what is installed, and "
    "classify_document to preview how a file would be routed."
)


def _get_router() -> EngineRouter:
    """Router over every importable engine (module-level so tests can stub it)."""
    from docfold.cli import _build_router

    return _build_router()


def _fetch_url(url: str) -> Path:
    """Download *url* to a temp file, preserving the extension for routing."""
    suffix = Path(urllib.parse.urlparse(url).path).suffix or ".bin"
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="docfold-")
    with urllib.request.urlopen(url) as response, open(fd, "wb") as fh:
        fh.write(response.read())
    return Path(name)


def _result_payload(result: EngineResult) -> dict[str, Any]:
    """EngineResult → JSON-safe dict, dropping bulky/binary slots."""
    return {
        "content": result.content,
        "format": result.format.value,
        "engine": result.engine_name,
        "pages": result.pages,
        "tables": result.tables,
        "confidence": result.confidence,
        "processing_time_ms": result.processing_time_ms,
    }


def _error_payload(exc: Exception) -> dict[str, Any]:
    """Honest structured failure — never garbage posing as content."""
    message = str(exc)
    match = re.match(r"All engines failed for .*\. Errors: (.*)", message)
    if match:
        failures = [part.strip() for part in match.group(1).split(";") if part.strip()]
        return {"error": "all engines failed", "failures": failures}
    return {"error": message, "failures": []}


async def _process(path_or_url: str, engine: str | None, output_format: str) -> dict[str, Any]:
    """Shared parse path: materialize URL → route → structured payload."""
    from docfold.engines.base import OutputFormat

    downloaded: Path | None = None
    try:
        if path_or_url.startswith(("http://", "https://")):
            downloaded = _fetch_url(path_or_url)
            file_path = str(downloaded)
        else:
            file_path = path_or_url
            if not Path(file_path).exists():
                return {"error": f"file not found: {file_path}", "failures": []}
        result = await _get_router().process(
            file_path, output_format=OutputFormat(output_format), engine_hint=engine
        )
        return _result_payload(result)
    except Exception as exc:  # noqa: BLE001 — every failure must come back structured
        return _error_payload(exc)
    finally:
        if downloaded is not None:
            downloaded.unlink(missing_ok=True)


def build_server() -> FastMCP:
    """Construct the FastMCP server. Raises ImportError if ``mcp`` is missing."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("docfold", instructions=_INSTRUCTIONS)

    @server.tool()
    async def parse_document(
        path_or_url: str,
        engine: str | None = None,
        output_format: str = "markdown",
    ) -> dict[str, Any]:
        """Parse a document (local path or URL) into structured output.

        Args:
            path_or_url: Local file path or http(s) URL of the document.
            engine: Optional engine name (see list_engines). Default: auto-route.
            output_format: markdown | html | json | text.
        """
        return await _process(path_or_url, engine, output_format)

    @server.tool()
    async def extract_tables(
        path_or_url: str,
        engine: str | None = None,
    ) -> dict[str, Any]:
        """Extract tables from a document as lists of row dicts.

        Args:
            path_or_url: Local file path or http(s) URL of the document.
            engine: Optional engine name. Default: auto-route.
        """
        payload = await _process(path_or_url, engine, "markdown")
        if "error" in payload:
            return payload
        return {
            "tables": payload["tables"] or [],
            "engine": payload["engine"],
            "pages": payload["pages"],
        }

    @server.tool()
    def list_engines() -> dict[str, Any]:
        """List registered engines with availability and supported extensions."""
        engines = [
            {"name": e["name"], "available": e["available"], "extensions": e["extensions"]}
            for e in _get_router().list_engines()
        ]
        return {"engines": engines}

    @server.tool()
    async def classify_document(path: str) -> dict[str, Any]:
        """Classify a local file for routing: pdf_text, pdf_scanned, office, image, …"""
        from dataclasses import asdict

        from docfold.utils.pre_analysis import pre_analyze

        if not Path(path).exists():
            return {"error": f"file not found: {path}", "failures": []}
        try:
            return asdict(await pre_analyze(path))
        except Exception as exc:  # noqa: BLE001
            return _error_payload(exc)

    return server


def main() -> None:
    """Console-script entry point for ``docfold-mcp`` (stdio transport)."""
    try:
        server = build_server()
    except ImportError:
        print(_INSTALL_HINT, file=sys.stderr)
        sys.exit(2)
    server.run()


if __name__ == "__main__":
    main()

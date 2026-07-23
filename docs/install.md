# docfold — agent setup instructions

You are an AI agent setting up **docfold** for your user. docfold turns any
document (PDF, DOCX, XLSX, PPTX, HTML, images, …) into structured, LLM-ready
markdown/JSON through one interface over 20+ parsing engines. Follow the
steps below **exactly and in order**, then report what you installed and
verified.

Ground rules:

- **Idempotent:** check before you change. Never reinstall what is installed,
  never overwrite an existing config — only add to it.
- **Honest:** if a step fails, say which step and show the error. Do not
  pretend a step succeeded.

## 1. Check if docfold is already installed

```bash
docfold --version
```

If this prints a version, docfold is installed — **do NOT reinstall**,
skip to step 3.

## 2. Install

```bash
pip install "docfold[mcp,pymupdf]"
```

Notes:
- Requires Python >= 3.10.
- `[mcp]` includes the MCP server; `[pymupdf]` is the fast local PDF engine —
  a good zero-config default. Plain `pip install docfold` is enough for
  library-only use.
- Every engine is an optional extra, e.g.
  `pip install "docfold[docling,marker]"` or `"docfold[all]"`. See
  `docfold engines` for the full list.

## 3. Verify the CLI

```bash
docfold doctor
docfold convert some-document.pdf
```

`doctor` prints the version, whether the MCP extra is present, and per-engine
availability. All subcommands:

```bash
docfold convert <file> [-e pymupdf] [-f markdown|html|json|text] [-o out.md]
docfold engines
docfold compare <file> [-e pymupdf,docling]
docfold evaluate <dataset-dir> [-e engines] [-o report.json]
docfold install [claude|codex|cursor|vscode|generic]
docfold doctor [--json]
docfold update [--check] [--extras mcp,docling] [--json]
```

`--json` (where offered) emits a single machine-parseable JSON document.
Errors are fatal with a non-zero exit code.

## 4. Register the MCP server (one command)

Pick the client you are running in:

```bash
docfold install claude    # Claude Code  (runs: claude mcp add docfold -- docfold-mcp)
docfold install codex     # Codex CLI    (runs: codex mcp add docfold -- docfold-mcp)
docfold install cursor    # Cursor       (merges ~/.cursor/mcp.json)
docfold install vscode    # VS Code      (runs: code --add-mcp ...)
docfold install generic   # prints the JSON below for any other client
```

`docfold install` is safe to re-run: it merges configs in place, preserves
every existing server, and is a no-op if docfold is already registered.

If your client is not listed, **read the client's MCP config first, then add
this entry to it — preserve all existing content**:

```json
{
  "mcpServers": {
    "docfold": {
      "command": "docfold-mcp",
      "args": []
    }
  }
}
```

The server speaks stdio and exposes four tools:

| Tool | Purpose |
|---|---|
| `parse_document(path_or_url, engine?, output_format?)` | File or URL → structured markdown/html/json/text |
| `extract_tables(path_or_url, engine?)` | Tables as lists of row dicts |
| `list_engines()` | Registered engines + availability |
| `classify_document(path)` | Routing category (pdf_text, pdf_scanned, office, image, …) |

## 5. Verify the MCP server

Tell the user to restart the client (MCP servers load on startup). After
restart, confirm the `docfold` server is connected and call `list_engines` —
it should return engine names such as `pymupdf`, `docling`, `marker`.

## 6. Report what you did

End with a short setup report:

- Installed docfold, or found version X already installed (step 1/2)
- `docfold doctor` result: N/M engines available, MCP extra yes/no (step 3)
- Which client you registered the MCP server in, and how (step 4)
- Whether the MCP connection was verified, or that a client restart is
  still pending (step 5)

## 7. Python API (optional)

```python
import asyncio
from docfold import EngineRouter
from docfold.engines.pymupdf_engine import PyMuPDFEngine

async def main():
    router = EngineRouter([PyMuPDFEngine()])
    result = await router.process("document.pdf")
    print(result.content)

asyncio.run(main())
```

## Links

- GitHub: https://github.com/mihailorama/docfold
- PyPI: https://pypi.org/project/docfold/
- Changelog: https://github.com/mihailorama/docfold/blob/main/CHANGELOG.md

---
purpose: "Agent-first distribution: MCP server, install/doctor/update CLI, agent onboarding docs, landing page, release tooling"
status: "DONE"
priority: "P1"
created: "2026-07-23"
---

# Feature: AGENT_DISTRIBUTION

## Problem

docfold is installable from PyPI but invisible to AI agents: no MCP server, no
one-command client registration, no agent-readable setup instructions, no
landing page. scrapefold already ships this stack (merged to main, live on
scrapefold.com) and it is the reference implementation for this task.

## Proposed Solution

Port the scrapefold distribution stack, adapted to docfold's zero-dependency
core (argparse instead of Typer, stdlib urllib instead of httpx):

1. **MCP server** `docfold-mcp` (`src/docfold/mcp_server.py`) on FastMCP
   (official `mcp` SDK, new optional extra `[mcp]`). Four tools:
   - `parse_document(path_or_url, engine?, output_format?)` — file or URL →
     structured markdown/html/json/text via `EngineRouter.process`.
   - `extract_tables(path_or_url, engine?)` — tables from `EngineResult.tables`.
   - `list_engines()` — registered engines with availability.
   - `classify_document(path)` — `utils.pre_analyze` category for routing.
   Without the extra: exit 2 with an install hint. Errors are structured
   (`{"error", "failures": [...]}`), never garbage-as-content. Tool
   definitions capped by a token-budget test (≈750–1000 tokens, chars/4).
2. **CLI subcommands** in the existing argparse CLI:
   - `docfold install <client>` — claude | codex | cursor | vscode | generic;
     runs `claude mcp add …` / merges `~/.cursor/mcp.json` preserving foreign
     servers (logic in new `src/docfold/install.py`).
   - `docfold doctor [--json]` — version, mcp extra, per-engine availability.
   - `docfold update [--check] [--extras …] [--json]` — self-update via PyPI
     (new `src/docfold/update.py`, stdlib urllib).
   - `docfold --version`.
3. **Agent onboarding**: `docs/install.md` (idempotent step-by-step for an AI
   agent), `docs/llms.txt`, `docs/.nojekyll`.
4. **Landing** `docs/index.html` (GitHub Pages from `docs/` on main), dark
   theme on the scrapefold CSS skeleton; hero CTA hierarchy: copy-setup-prompt
   button + `fetch …/install.md` line first, `pip install docfold` chip second,
   GitHub/PyPI as small links. A11y: sticky nav + anchors, skip-link,
   focus-visible, aria-live on copy buttons, prefers-reduced-motion. OG card
   PNG 1200×630. Headless-Chromium screenshot check at 1280px and 390px.
5. **Release tooling**: hatch dynamic version from `__init__.py` (fixes the
   current 0.6.13 vs 0.6.0 drift), `.github/workflows/tag-release.yml`
   (workflow_dispatch tag creation + manual CI dispatch on the tag), README /
   CHANGELOG / CONTRIBUTING release checklist.

## Affected Files

- `src/docfold/mcp_server.py` — new: FastMCP server + tools
- `src/docfold/install.py` — new: install plan / mcp.json merge logic
- `src/docfold/update.py` — new: PyPI version check + pip upgrade argv
- `src/docfold/cli.py` — add install/doctor/update/--version
- `src/docfold/__init__.py` — version becomes single source of truth
- `pyproject.toml` — `[mcp]` extra, `docfold-mcp` script, dynamic version
- `docs/index.html`, `docs/install.md`, `docs/llms.txt`, `docs/.nojekyll`,
  `docs/assets/og-card.png` — new
- `.github/workflows/tag-release.yml` — new
- `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md` — docs

## Test Plan

### Unit / Functional Tests

- [x] `test_mcp_server.py`: exit 2 + hint without `mcp`; four tools
      registered; parse_document happy path (monkeypatched router);
      URL input downloads to temp file; structured failure payload;
      extract_tables returns tables / empty list; classify_document;
      token budget ≤ 1000 (chars/4 estimate)
- [x] `test_install.py`: plans for all five clients; cursor merge preserves
      foreign servers; idempotent re-run; unknown client raises
- [x] `test_update.py`: is_newer comparisons; build_update_argv with extras;
      latest_version parses PyPI JSON (mocked)
- [x] `test_cli.py`: doctor text/JSON; install --print-only / --json;
      update --check --json (mocked); --version

### Integration / E2E Tests

- [x] Real stdio round-trip: spawn `docfold-mcp`, list tools (requires mcp
      extra; skipped otherwise)
- [x] Landing rendered in headless Chromium at 1280/390, screenshots reviewed

### Test Commands

```bash
pytest tests/ -m "not slow"
pytest tests/test_mcp_server.py tests/test_install.py tests/test_update.py -v
```

## Edge Cases

- `mcp` extra missing → `docfold-mcp` exits 2 with install hint; `doctor`
  reports it, CLI otherwise unaffected.
- Cursor `mcp.json` absent / empty / has other servers → create / merge,
  never clobber; malformed `mcpServers` → clear error.
- Client CLI (claude/codex/code) not on PATH → print the command instead of
  failing.
- URL input unreachable → structured error, no partial content.
- All engines unavailable → parse_document returns structured failure listing
  attempted engines.

## Out of Scope

- New engines or router changes.
- Publishing the release (Mike merges and releases explicitly).
- Custom domain purchase; CNAME set only after Mike picks the domain.

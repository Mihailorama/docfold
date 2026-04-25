---
purpose: "Integrate Microsoft's markitdown as a new docfold engine and include it in the benchmark harness."
status: "IN_PROGRESS"
priority: "P1"
created: "2026-04-24"
---

# Feature: markitdown engine adapter + benchmark coverage

## Problem

Microsoft ships [markitdown](https://github.com/microsoft/markitdown), a pure-Python
library that converts a wide range of formats (PDF, DOCX, PPTX, XLSX, HTML, CSV,
JSON, XML, images, audio, ePub, ZIP, YouTube URLs) into LLM-friendly Markdown.
It is MIT-licensed, has no heavy runtime, and is a sensible "lowest common
denominator" baseline that users expect docfold to support alongside Docling,
Marker, Unstructured, etc. Today there is no adapter, no extras group, and it
does not appear in `benchmark.py`.

Task from the user: "connect it and run benches" — so we need both the adapter
and synthetic-PDF benchmark coverage comparable to the other local engines.

## Proposed Solution

1. New `MarkItDownEngine` adapter under `src/docfold/engines/markitdown_engine.py`
   that conforms to the `DocumentEngine` ABC:
   - Lazy-imports `markitdown` (keeps the base package dep-free).
   - Calls `MarkItDown().convert(file_path)` inside an executor (the library's
     API is synchronous).
   - Returns an `EngineResult` with `format=OutputFormat.MARKDOWN` (markitdown
     always emits Markdown; for `HTML`/`JSON`/`TEXT` we serialize the Markdown
     string into a minimal wrapper so the contract holds).
   - `is_available()` returns True only when `markitdown` is importable.
   - `capabilities` is empty — markitdown returns plain text, no bboxes.
2. New `markitdown` extras in `pyproject.toml`:
   `markitdown = ["markitdown[all]>=0.0.1"]` and add to `all = [...]`.
3. Register it in `engines/router.py` priority lists for the formats it
   handles (PDF, Office, HTML, images, CSV/text, ePub, ZIP) — placed near the
   Unstructured/Marker tier since it is a similar "convert to Markdown"
   baseline rather than a layout analyzer.
4. Wire it into `benchmark.py` as an additional candidate engine so it runs
   on the same 7 synthetic PDFs as the existing engines and reports CER/WER/
   time like the others.
5. Add a row for markitdown to the two engine tables in `README.md`.

## Affected Files

- `src/docfold/engines/markitdown_engine.py` — new adapter.
- `tests/engines/test_markitdown_engine.py` — new test file, mocks the
  `markitdown` package (tests do not require it installed).
- `src/docfold/engines/router.py` — add `"markitdown"` to extension priority
  lists and the default fallback.
- `pyproject.toml` — add `markitdown` extras, include in `all`.
- `benchmark.py` — import and register `MarkItDownEngine` in the candidate
  list.
- `README.md` — add markitdown row to the two engine overview tables.

## Test Plan

### Unit / Functional Tests

- [ ] `test_name` — engine name is `"markitdown"`.
- [ ] `test_supported_extensions` — covers PDF, DOCX, PPTX, XLSX, HTML, images,
      CSV, JSON, XML, ePub.
- [ ] `test_capabilities_defaults_to_empty` — no bboxes/confidence etc.
- [ ] `test_is_available_true_when_importable` — patched import succeeds.
- [ ] `test_is_available_false_when_missing` — `ImportError` short-circuits.
- [ ] `test_process_markdown_returns_engine_result` — mock the `MarkItDown`
      class so `convert(...).text_content` is a known Markdown string; assert
      the `EngineResult` fields (content, format, engine_name, time).
- [ ] `test_process_runs_convert_in_executor` — the synchronous `convert` call
      must be dispatched via `loop.run_in_executor` so we don't block the
      event loop.
- [ ] `test_process_missing_dependency_raises` — when markitdown isn't
      installed, `.process()` should raise a clear `RuntimeError` (or similar)
      so callers see *why* it failed.

### Integration / E2E Tests

- [ ] `benchmark.py` runs on a host where `markitdown` is installed and
      produces a row for it in the summary table.

### Test Commands
```bash
# Run just the new engine tests
pytest tests/engines/test_markitdown_engine.py -v

# Full suite (should stay green)
pytest tests/

# E2E benchmark (requires: pip install docfold[markitdown])
python benchmark.py
```

## Edge Cases

- `markitdown` not installed on CI — tests must mock the import path and not
  require the real dependency (mirrors `test_liteparse_engine.py`).
- `OutputFormat.HTML` / `JSON` / `TEXT` — markitdown only produces Markdown.
  We honor the request by wrapping the Markdown string (HTML: wrap in
  `<pre>`; JSON: `{"markdown": "..."}`; TEXT: pass through).
- Unicode / CJK / RTL documents — ensure the string is passed through without
  encoding munging (the benchmark's Arabic/Hebrew/Chinese fixtures will
  cover this in the E2E run).

## Out of Scope

- No plugin hooks for markitdown's extensibility system (custom converters).
- No attempt to extract bounding boxes — markitdown doesn't produce them.
- No audio / YouTube / ZIP extensions enrollment in the router priority map;
  we only register formats that already exist in `_EXTENSION_PRIORITY`.

## Follow-up: non-PDF benchmark coverage

The first round of `benchmark.py` only generated PDFs, which is the format
where markitdown is *least* differentiated (PyMuPDF dominates on digital text
PDFs). To actually exercise where markitdown shines, the harness now also
produces:

- A synthetic **DOCX** (built via stdlib `zipfile` + minimal Word XML — no
  new runtime deps).
- A synthetic **HTML** page with a heading, paragraphs, and a small table.
- A synthetic **CSV** with a few rows.

Engines are filtered per-doc by `supported_extensions`, so PyMuPDF / OCR
engines simply don't run on Office / web / tabular fixtures (instead of
spamming the report with errors).

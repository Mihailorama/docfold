---
purpose: "Add OpenDataLoader PDF as a local, fast PDF structuring engine."
status: "OPEN"
priority: "P2"
created: "2026-04-16"
---

# Feature: OpenDataLoader PDF Engine

## Problem
docfold already ships several local PDF engines (PyMuPDF, LiteParse, Docling, MinerU, …),
but none of them are based on `opendataloader-pdf` — a popular, Apache-2.0 Java tool
(16.8k stars on GitHub) exposed through a thin Python wrapper on PyPI
(`opendataloader-pdf`).

Why add it now:
- Very fast deterministic layout + reading-order extraction on CPU (benchmarked
  at 100+ pages/sec by upstream) — useful as a reliable, low-latency baseline
  to compare against heavier OCR / ML engines.
- Emits richly typed structural elements (`heading`, `paragraph`, `table`,
  `list`, `header`, `footer`, …) with per-element bounding boxes and page
  numbers — a good fit for the docfold `EngineResult` contract.
- Users can opt into a hybrid AI mode later without changing the adapter.

## Proposed Solution
Implement a new engine adapter `OpenDataLoaderEngine` that wraps the
`opendataloader-pdf` Python package. The engine will:

1. Write output (`json` + requested format) to a temp directory via
   `opendataloader_pdf.convert(...)`.
2. Read back the produced files:
   - For `MARKDOWN` — read the `.md` file (or `text` output).
   - For `HTML` — read the `.html` file.
   - For `JSON`/`TEXT` — use the JSON/text file directly.
3. Parse the JSON output to build a flat list of `BoundingBox` entries by
   recursively walking the nested `kids` tree. Map upstream types
   (`heading`, `paragraph`, `table`, `list`, `header`, `footer`, …) to
   docfold's `BoundingBox.type` names (`SectionHeader`, `Text`, `Table`,
   `List`, …).
4. Normalize PDF-point coordinates — upstream emits `[x1, y1, x2, y2]` in
   PDF points; we pass them through unchanged (same as PyMuPDF).

Capabilities advertised: `bounding_boxes=True`, `reading_order=True`,
`heading_detection=True`, `table_structure=True`.

## Affected Files
- `src/docfold/engines/opendataloader_engine.py` — new adapter
- `tests/engines/test_opendataloader_engine.py` — new tests (mocked subprocess)
- `benchmark.py` — register the new engine alongside the existing ones
- `pyproject.toml` — add `opendataloader = ["opendataloader-pdf>=2.2"]` extra,
  include it in `[all]`
- `README.md` / `CHANGELOG.md` — short mention (optional in this task)

## Test Plan

### Unit / Functional Tests
- [x] `name` is `"opendataloader"`
- [x] `supported_extensions` includes `"pdf"`
- [x] `capabilities` advertises `bounding_boxes`, `reading_order`,
      `heading_detection`, `table_structure`
- [x] `is_available()` returns True when `opendataloader_pdf` imports and
      `java` is on PATH; False otherwise
- [x] `process()` returns an `EngineResult` with the correct `engine_name`,
      `format`, non-empty `content`, populated `pages`, non-empty
      `bounding_boxes`, and `processing_time_ms >= 0` — tested with a
      mocked `convert()` that materializes a fake output directory
- [x] JSON walker flattens nested `kids` into one `BoundingBox` per leaf
      element, preserving page numbers and bbox coords
- [x] `heading` → `SectionHeader`, `paragraph` → `Text`, `table` → `Table`,
      `list` → `List` type mapping
- [x] Errors from the underlying CLI surface as `RuntimeError`

### Integration / E2E Tests
- [x] `benchmark.py` discovers the engine when `opendataloader-pdf` and
      Java are installed and reports CER/WER/time/bbox counts alongside the
      other engines.

### Test Commands
```bash
pytest tests/engines/test_opendataloader_engine.py -v
pytest tests/                      # full suite still green
python benchmark.py                # sanity check
```

## Edge Cases
- `java` not installed → `is_available()` returns False, no crash.
- Encrypted PDF without password → surface upstream error as `RuntimeError`.
- Empty PDF / no elements → `bounding_boxes` is `None`, `content` is `""`.
- Pages without any `kids` → still counted via `"number of pages"`.
- Deeply nested `kids` (tables / lists) → recursion handles arbitrary depth.

## Out of Scope
- Hybrid AI mode (`hybrid=…`) — can be added later via kwargs.
- Image extraction / annotated-PDF output.
- Table structure parsing into `tables` list of dicts (bboxes only for now).

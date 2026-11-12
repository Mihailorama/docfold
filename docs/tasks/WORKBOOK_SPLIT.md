---
purpose: "Split a workbook per sheet; xlsx to CSV and HTML"
status: "DONE"
priority: "P3"
created: "2026-11-12"
---

# Feature: Workbook split and CSV/HTML output (DOCFOLD-23)

## Problem
Per-sheet processing needs one file per sheet, and some consumers want CSV or
an HTML table (with clickable links) instead of TSV text.

## Proposed Solution
In `docfold.engines.spreadsheet_engine`:
- `split_workbook(path, out_dir) -> list[str]`: one values-only `.xlsx` per
  sheet; unsafe file-name characters become `_`, duplicates get `_2`, `_3`.
- `workbook_to_csv(path) -> {sheet: csv_text}`.
- `read_sheets(path)`: shared reader.
- `SpreadsheetEngine` HTML output: one `<table>` per sheet, `<h2>` sheet name
  when several, values escaped, http(s) values as links.

## Test Plan
- [x] split names, duplicates, values round-trip
- [x] CSV quoting and empty cells
- [x] HTML escaping, links, sheet headers

```bash
pytest tests/engines/test_spreadsheet_engine.py -v
```

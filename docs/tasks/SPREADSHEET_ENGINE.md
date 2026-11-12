---
purpose: "Spreadsheet values keep sheet + cell coordinates; CSV becomes JSON records"
status: "DONE"
priority: "P1"
created: "2026-11-12"
---

# Feature: Spreadsheet engine with cell coordinates (DOCFOLD-15)

## Problem
xlsx goes through docling / markitdown, which return a table as text and drop
where each value came from. Provenance of an extracted value needs the sheet
name and the cell (`Sheet1!B7`). CSV has no records output.

## Proposed Solution
New `SpreadsheetEngine` (`name="spreadsheet"`, extra `[spreadsheet]` =
openpyxl) for `xlsx`, `xlsm`, `csv`, `tsv`:
- text output: one TSV block per sheet, `Sheet: <name>` header when the
  workbook has several sheets; CSV/TSV text is returned as is.
- `metadata["cell_map"]`: one entry per non-empty cell: `sheet`, `cell`
  (A1), `tsv_row` (row index across all sheets), `tsv_col`, `value`
  (first 100 chars). Capped at 200,000 entries (`cell_map_truncated`).
- `metadata["sheets"]`: sheet names in order.
- JSON output: records. CSV/TSV: list of row dicts (delimiter sniffed from
  `, ; \t |`). xlsx: `{sheet: [row dicts]}`, first row is the header.
- `docfold.engines.spreadsheet_engine.csv_to_records(text)` for callers that
  already hold the CSV text.
- Router: added last in the xlsx/csv/tsv priority lists, so existing routing
  does not change; select it with `engine_hint="spreadsheet"`.

## Affected Files
- `src/docfold/engines/spreadsheet_engine.py` (new)
- `src/docfold/engines/router.py` - priority lists
- `src/docfold/cli.py` - registration
- `pyproject.toml` - `[spreadsheet]` extra, openpyxl in `[test]`

## Test Plan
- [x] multi-sheet xlsx: TSV text, sheet headers, cell_map coordinates and tsv rows
- [x] single sheet: no header line
- [x] JSON records for xlsx and CSV (`;` delimiter sniffed), TSV
- [x] cell_map cap

```bash
pytest tests/engines/test_spreadsheet_engine.py -v
```

## Edge Cases
- Empty cells: kept as empty TSV fields, absent from cell_map.
- Formulas: cached values (`data_only=True`); a workbook never saved by Excel
  has no cached values and yields empty cells.
- `.xls` (BIFF) is not supported by openpyxl; it stays with docling/markitdown.

## Out of Scope
- Per-sheet split to CSV/HTML files (DOCFOLD-23).

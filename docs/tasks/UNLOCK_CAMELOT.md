---
purpose: "Remove PDF protection; extract tables with Camelot"
status: "DONE"
priority: "P3"
created: "2026-11-12"
---

# Feature: PDF unlock and Camelot tables (DOCFOLD-20)

## Problem
Protected PDFs (copy/print restrictions or a user password) break some
engines. Whitespace-separated tables are often lost by layout engines.

## Proposed Solution
- `docfold.preprocessing.unlock_pdf(path, out_path=None, password="")`:
  returns the path itself when unprotected, else a decrypted copy via
  `qpdf --decrypt` (when on PATH) or PyMuPDF. Wrong/missing user password ->
  `ValueError`. `is_protected(path)` also sees owner-password-only files.
- `CamelotEngine(flavor="stream", pages="all", **camelot_kwargs)` (`camelot`,
  extra `[camelot]`): tables with `page`, `bbox` (top-left origin, PDF points),
  `accuracy` (0-1), `cells`, `records`; `Table` bounding boxes; content is the
  tables as Markdown / HTML / JSON. Not in any default priority list.

## Test Plan
- [x] unlock: plain, owner-password, user password right/wrong (PyMuPDF; qpdf path when installed)
- [x] Camelot with a fake module: cleaning, records, bbox flip, outputs
- [x] Camelot real on a generated table PDF (skipped without camelot)

```bash
pytest tests/test_unlock_camelot.py -v
```

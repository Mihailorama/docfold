---
purpose: "Check extracted text with an LLM: internal consistency and source pages"
status: "DONE"
priority: "P3"
created: "2026-11-12"
---

# Feature: LLM validation of extracted text (DOCFOLD-24)

## Problem
Extraction can silently drop rows, misread numbers or break tables. A cheap
LLM pass can flag totals that do not add up and content missing compared with
the page images.

## Proposed Solution
`docfold.validate.validate_extraction(text, models, *, file_path=None,
acompletion=None, context=..., visual=True, max_pages=3)` -> `ValidationResult`
(`is_valid`, `issues`, `checks`, `skipped`, `model`):
1. consistency check on the text (counts, totals, formats, references, logic);
2. visual check: first pages rendered as JPEG next to the text (skipped for
   documents longer than `max_pages`).
Issues carry `type`, `severity`, `description`, `location`, `expected_value`,
`actual_value`, `source`. `is_valid` is False on any critical/major issue,
None when no check ran. Ordered model fallback; unparseable answers count as a
failed model.

## Test Plan
- [x] both checks, issue mapping, images sent, context in prompt
- [x] minor-only issues valid; visual skipped over the page limit
- [x] fallback chain; all fail; non-JSON answer

```bash
pytest tests/test_validate.py -v
```

## Out of Scope
- Auto-fix of the text (see DOCFOLD-21 OCR correction).

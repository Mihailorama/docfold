---
purpose: "Per-page text/image classification and PDF metadata"
status: "DONE"
priority: "P3"
created: "2026-11-12"
---

# Feature: Per-page classification and PDF metadata (DOCFOLD-22)

## Problem
`pre_analyze` decides "text vs scanned" for the whole file from the first two
pages. Mixed PDFs (digital pages plus scanned annexes) need a per-page answer,
and callers also want basic document facts (encryption, title/author, forms).

## Proposed Solution
In `docfold.utils.pre_analysis` (PyMuPDF):
- `classify_pages(path) -> list[str]`: one of `text`, `image`, `mixed`,
  `empty` per page, from the areas of text and image blocks.
- `pdf_metadata(path, sample_pages=5) -> dict`: `page_count`, `encrypted`,
  `needs_password`, `title`, `author`, `creator`, `producer`,
  `creation_date`, `content_types` (`text`, `images`, `tables`, `forms`,
  `annotations` seen on the sampled pages), `has_forms`, `has_annotations`,
  `is_scanned` (True: images only, False: text only, None: mixed/unknown).

## Test Plan
- [x] text, image, mixed and empty pages
- [x] metadata fields, forms, encrypted file

```bash
pytest tests/utils/test_pre_analysis.py -v
```

## Out of Scope
- Document complexity score (depends on the caller's processing stats).

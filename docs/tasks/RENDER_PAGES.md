---
purpose: "Public page-image rendering for PDFs, images and office files"
status: "DONE"
priority: "P1"
created: "2026-11-12"
---

# Feature: `render_pages` (DOCFOLD-14)

## Problem
Callers need page images for vision steps and for showing the source next to
extracted text with bounding boxes. docfold renders pages only inside engines
(`vlm_ocr_engine._page_images`), always as PNG and always all pages. PNG
encoding dominates the time (about 1 s per page at 150 dpi), and a full
base64 list of a long document sits in memory.

## Proposed Solution
`docfold.render.render_pages(path, pages=None, *, dpi=150, image_format="png",
quality=85)` yields `(page_number, image_bytes)` one page at a time:
- `pages`: `"1-3,7"` or an iterable of 1-based numbers; `None` = all.
- `image_format`: `png`, `jpeg` or `webp`; Pillow (in `[render]`) encodes jpeg about 5x faster than PNG and is required for webp.
  `quality` applies to jpeg/webp.
- PDFs and images open with PyMuPDF; office files (docx, pptx, xlsx, odt, rtf,
  ...) convert to PDF with LibreOffice (`soffice`) in a temp dir first, and
  the temp dir is removed when the generator closes.

## Affected Files
- `src/docfold/render.py` (new); `[render]` extra = PyMuPDF.

## Test Plan
- [x] all pages, PNG bytes, 1-based numbers
- [x] page subset from spec string and from a list; out-of-range pages skipped
- [x] jpeg smaller than png; quality changes size; webp (skipped without Pillow)
- [x] dpi changes pixel size
- [x] image input renders one page
- [x] office input without LibreOffice raises a clear error (soffice mocked)
- [x] lazy: nothing rendered before iteration

```bash
pytest tests/test_render.py -v
```

## Edge Cases
- Unknown `image_format`: `ValueError`.
- LibreOffice conversion failure or timeout: `RuntimeError`.

## Out of Scope
- Async wrapper (run the generator in an executor).

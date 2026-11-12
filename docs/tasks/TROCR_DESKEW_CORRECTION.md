---
purpose: "TrOCR engine, image deskew pre-step, LLM post-OCR correction"
status: "DONE"
priority: "P3"
created: "2026-11-12"
---

# Feature: TrOCR, deskew and LLM OCR correction (DOCFOLD-21)

## Proposed Solution
- `TrOCREngine(model="microsoft/trocr-base-printed", dpi=200, batch_size=16,
  device=None)` (`trocr`, extra `[trocr]`): page images (PDF via
  `render_pages`) cut into text lines with a horizontal projection profile
  (`split_lines`), lines OCR'd in batches; `Line` bounding boxes in page pixels.
  Not in any default priority list.
- `docfold.preprocessing.deskew`: `estimate_skew(image)` (coarse 0.5 deg search
  over +-10 deg, then 0.05 deg refinement, maximizing row-sum variance) and
  `deskew_image(src, dst=None)` (skips angles under 0.2 deg). Pillow + NumPy.
- `docfold.vision.correct_ocr_text(text, models, acompletion=..., image_b64=None)`:
  LLM fixes OCR errors only, with the page image when given; ordered model
  fallback; returns the input when all models fail.

## Test Plan
- [x] skew estimate on straight and rotated synthetic pages; deskew output
- [x] line split; TrOCR engine with a fake transformers module
- [x] correction with fallback and failure

```bash
pytest tests/test_ocr_extras.py -v
```

## Out of Scope
- Downloading a real TrOCR checkpoint in CI.

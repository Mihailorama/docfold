---
purpose: "Add layout (bboxes, captions, images) from a second engine when another engine wins on text"
status: "DONE"
priority: "P1"
created: "2026-11-12"
---

# Feature: Primary + supplement merge (DOCFOLD-13)

## Problem
The engine with the best text is often not the one with the best layout. A
text layer (pymupdf) or docling can win on text, while marker gives typed
block bounding boxes, image captions and page images. Callers run the second
engine themselves and graft its layout onto the first result.

## Proposed Solution
`EngineRouter.process(..., supplement_engine="marker")`: after the primary
result is chosen (with or without the quality gate), run the supplement
engine unless it produced the primary. Keep the primary `content`, `format`,
`engine_name`, `pages`, `confidence`, `processing_time_ms`; take from the
supplement:
- `bounding_boxes` (only when the supplement returned some)
- `images` (supplement's, else the primary's)
- `tables` (primary's, else the supplement's)
- `metadata`: primary's updated with the supplement's (e.g. `marker_json`)

The attempt is appended to `fallback_chain` with `role="bbox_supplement"`,
`selected=False`. A failing or unavailable supplement is recorded (`error` /
`skip_reason`) and never fails the call. The supplement runs only when it
supports the file extension.

## Affected Files
- `src/docfold/engines/router.py`

## Test Plan
- [x] bboxes, images, metadata grafted; primary text kept; chain entry
- [x] skipped when the supplement is the primary engine
- [x] supplement error / unavailable / unsupported extension: primary returned
- [x] no bboxes from supplement: primary bboxes kept
- [x] works together with the quality gate

```bash
pytest tests/engines/test_router_supplement.py -v
```

## Out of Scope
- Re-aligning supplement boxes to primary text spans.

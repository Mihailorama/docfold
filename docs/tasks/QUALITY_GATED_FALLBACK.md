---
purpose: "Router falls back on poor output, not only on exceptions, and reports every attempt"
status: "DONE"
priority: "P1"
created: "2026-11-12"
---

# Feature: Quality-gated fallback + `fallback_chain` (DOCFOLD-11)

## Problem
`EngineRouter.process` moves to the next engine only when an engine raises. A
text-layer engine that returns almost nothing for a scanned PDF, or an engine
that embeds page images as base64 `<img>` tags instead of doing OCR, is
accepted as is. Callers that need a retry have to re-implement the chain
themselves and also lose the record of what was tried.

## Proposed Solution
- `EngineResult.fallback_chain`: one dict per attempt, filled by
  `EngineRouter.process`: `engine`, `chars` (after base64 strip), `confidence`,
  `processing_time_ms`, `selected`, `role` (`primary` / `fallback`) and, when
  relevant, `skip_reason` or `error`.
- `EngineRouter.process(..., quality_gate=None, fallback_engines=None)`:
  - `quality_gate(result, file_path) -> str | None` returns a rejection reason.
    A rejected result is kept as a candidate; the next engine runs. A later
    result is accepted when it passes the gate and has more real text than
    every earlier attempt. If nothing passes, the attempt with the most real
    text is returned.
  - `fallback_engines` sets the retry order explicitly (after the hinted or
    selected primary). Unregistered or unavailable engines are recorded with
    `skip_reason="engine_unavailable"`. Without it, the existing behaviour
    holds: no fallback with `engine_hint`, the extension priority chain
    otherwise.
- `docfold.utils.quality`: `strip_base64_images`, `base64_ratio` and
  `default_quality_gate` (chars per page for PDFs/images, base64 ratio
  >= 0.9, `quality_ok` confidence and gibberish checks, and the image-page
  check on text-layer engine output).

## Affected Files
- `src/docfold/engines/base.py` - `fallback_chain` field
- `src/docfold/engines/router.py` - gated fallback loop
- `src/docfold/utils/quality.py` - base64 helpers, default gate

## Test Plan
- [x] attempts recorded without a gate (backward compatible path)
- [x] gate rejection moves to the next engine; reason in `skip_reason`
- [x] exceptions recorded as `error`
- [x] best attempt returned when nothing passes the gate
- [x] explicit `fallback_engines` after `engine_hint`, unavailable engines recorded
- [x] base64 stripping / ratio; default gate on real PDFs (text vs image page)

```bash
pytest tests/engines/test_router.py tests/utils/test_quality.py -v
```

## Edge Cases
- `engine_hint` without `fallback_engines` still raises on failure (unchanged).
- All attempts raise: `RuntimeError` as before.

## Out of Scope
- Script-aware routing (DOCFOLD-12): the caller passes `fallback_engines`.
- Supplement merge (DOCFOLD-13).

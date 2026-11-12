---
purpose: "Vision steps go through the caller's LLM gateway and model chain"
status: "DONE"
priority: "P1"
created: "2026-11-12"
---

# Feature: Injectable LLM caller for vision engines (DOCFOLD-17)

## Problem
`VLMOCREngine` posts to `/chat/completions` itself, and there is no image
captioning step at all. A caller that keeps model management, cost logging and
fallbacks in its own gateway cannot route these calls through it. `docfold.split`
already takes `acompletion`; the vision paths should too.

## Proposed Solution
- `VLMOCREngine(preset, acompletion=None)`: when given, each page goes through
  `await acompletion(model=..., messages=..., **params)` (LiteLLM-style
  response) instead of the HTTP client; the engine is available without a
  base URL. `process(..., model="...")` overrides the model per call.
- `docfold.vision.caption_images(images, models, *, acompletion=None,
  document_text="", min_image_bytes=5000, prompt=None)`: one batched vision
  call for all images bigger than the threshold; the answer is split per image
  by `[name]:` markers. `models` is an ordered fallback chain (LiteLLM names
  or kwargs dicts, as in `LLMPageClassifier`); `acompletion` defaults to
  `litellm.acompletion`. Returns `{name: text}`; all `""` when every model fails.

## Affected Files
- `src/docfold/engines/vlm_ocr_engine.py`, `src/docfold/vision.py` (new)

## Test Plan
- [x] VLM OCR with injected acompletion: per-page call, model override, postprocess, availability
- [x] captioning: batching, size filter, `[name]` parsing, single image, fallback chain, all-fail

```bash
pytest tests/test_vision.py tests/engines/test_vlm_ocr_engine.py -v
```

## Out of Scope
- Caching answers (caller's gateway).

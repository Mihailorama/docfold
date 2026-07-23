---
purpose: "Add Baidu Unlimited-OCR as a local VLM document-parsing engine"
status: "OPEN"
priority: "P2"
created: "2026-06-27"
---

# Feature: Unlimited-OCR Engine

## Problem
[Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) (released June 2026,
10.7k★, MIT-licensed code) is a new open-weight document-parsing VLM. It takes
DeepSeek-OCR as a baseline and replaces the decoder attention with **Reference
Sliding Window Attention (R-SWA)**, giving a *constant* KV cache across decoding.
Combined with DeepSeek-OCR's high-compression encoder, it can transcribe **dozens
of pages in a single forward pass** under a 32K context — the headline "one-shot
long-horizon parsing" capability. It outputs structured Markdown (headings,
tables, reading order) and is competitive on document-parsing benchmarks.

docfold already ships 20+ engine adapters (Chandra, Surya, MinerU, …) behind a
unified `DocumentEngine` interface. Adding Unlimited-OCR gives users a fresh,
free, locally-runnable VLM option — particularly for long, multi-page documents
where its constant-KV-cache design is an advantage. "Now" because the model just
shipped and there is clear user interest.

## Proposed Solution
Add a new `UnlimitedOCREngine` adapter that wraps the upstream HuggingFace model
(`baidu/Unlimited-OCR`, loaded with `trust_remote_code=True`), mirroring the
existing `ChandraEngine`/`SuryaEngine` adapters:

- Lazy-load the model + tokenizer on first `process()` call (never at import,
  construction, `is_available()`, or router-registration time).
- Run blocking inference inside `loop.run_in_executor` like the other local
  engines.
- Support the upstream **`gundam`** (base_size=1024, image_size=640,
  crop_mode=True) and **`base`** (base_size=1024, image_size=1024,
  crop_mode=False) modes via a `mode` constructor parameter.
- Accept images directly and render PDF pages to images (via PyMuPDF/`fitz`)
  before inference, like `ChandraEngine`.
- Emit Markdown / HTML / JSON / text from the unified `EngineResult`.

## Affected Files
- `src/docfold/engines/unlimited_ocr_engine.py` — NEW adapter.
- `src/docfold/engines/router.py` — add `unlimited_ocr` to PDF + image priority
  lists and the default fallback.
- `src/docfold/cli.py` — register the engine in `_build_router()`.
- `pyproject.toml` — add `unlimited-ocr` optional-dependency group; include in
  `all`.
- `tests/engines/test_adapters.py` — `TestUnlimitedOCREngine` + add to the
  `TestAllEnginesImplementInterface` parametrize list.
- `README.md`, `docs/benchmarks.md`, `CHANGELOG.md` — document the engine.

## Test Plan

### Unit / Functional Tests
- [ ] `test_name` — `name == "unlimited_ocr"`.
- [ ] `test_supported_extensions` — pdf + common image extensions present.
- [ ] `test_is_available_when_missing` — returns `bool` (False) when `torch`
      is unavailable.
- [ ] `test_config_stored` — constructor params stored (`_mode`, `_model`,
      `_max_length`, `_prompt`, `_device`).
- [ ] `test_default_mode_is_gundam` — `_mode` defaults to `"gundam"`.
- [ ] `test_mode_params` — `gundam` → (1024, 640, True); `base` → (1024, 1024, False).
- [ ] `test_capabilities` — table_structure / heading_detection / reading_order
      True; bounding_boxes / confidence False.
- [ ] `test_process_returns_engine_result` — mocked model produces a valid
      `EngineResult` (markdown).
- [ ] `test_process_json_output` — JSON output format wraps per-page text.
- [ ] Added to `TestAllEnginesImplementInterface` parametrize list.

### Integration / E2E Tests
- [ ] (manual, GPU) Run a real image and a multi-page PDF through the engine and
      verify Markdown output and page count.

### Test Commands
```bash
# Run the new engine tests
pytest tests/engines/test_adapters.py -k UnlimitedOCR -v

# Full suite (no regressions)
pytest tests/ -m "not slow"
```

## Edge Cases
- `torch` / `transformers` not installed → `is_available()` returns `False`,
  engine is simply not registered.
- PDF input with no PyMuPDF → raise a clear `ImportError` from the render step.
- Empty / unreadable page → model returns empty string; adapter keeps the page
  slot so page numbering stays correct.
- Model emits text only when `save_results=False`; adapter relies on the return
  value and uses a temp dir for any side-effect output.

## Out of Scope
- Native multi-page `infer_multi` long-horizon batching (single forward pass over
  many pages). The first cut processes page-by-page for determinism and
  testability; long-horizon batching is a future enhancement.
- Bounding-box extraction (the simple parse path returns Markdown only).
- vLLM serving backend.

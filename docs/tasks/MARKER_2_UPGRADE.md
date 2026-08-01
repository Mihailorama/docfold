---
purpose: "Surface Marker 2 (rewritten marker-pdf) and expose its mode axis in the local adapter"
status: "OPEN"
priority: "P2"
created: "2026-08-01"
---

# Feature: Marker 2 Upgrade

## Problem
Datalab shipped [Marker 2](https://www.datalab.to/blog/marker-2) (2026-07-20), a
rewrite of the open-source `marker-pdf`:

- Same PyPI package (`marker-pdf`) and **same Python API** docfold already calls
  (`PdfConverter(artifact_dict=create_model_dict())`, `converter(path)`,
  `text_from_rendered(...)`). So the rewrite is a drop-in `pip install -U marker-pdf`
  with zero code change - `MarkerLocalEngine` already targets it.
- New headline feature: a **mode axis** `balanced` / `fast` / `--disable_ocr`,
  auto-selected by device (balanced on GPU, fast on CPU). CPU is now fully
  supported (was GPU-oriented before).
- New `chunks` output format (RAG-friendly), and `--use_llm` for tables/math/forms.

Two gaps in the current adapters:

1. **`MarkerLocalEngine` does not expose `mode` as a first-class param and drops
   per-call kwargs.** `process()` ignores `**kwargs` (unlike `MarkerEngine`, the
   SaaS adapter, which merges per-call overrides). Only constructor `**kwargs`
   reach `config`. So the main new feature (CPU speed/accuracy tradeoff) is not
   reachable per-call.
2. **SaaS `MarkerEngine` defaults to `mode="accurate"`** (`marker_engine.py`),
   but Marker 2 renamed the axis to `balanced`/`fast`/`disable_ocr`. `accurate`
   may be deprecated in the hosted API - needs verification against
   https://documentation.datalab.to/ before it silently breaks the default call.

Docs also undersell Marker: the README engine table marks it `SaaS / Paid`, but
Marker 2 is free/local/CPU via `MarkerLocalEngine`.

## Proposed Solution
1. Add a `mode` param to `MarkerLocalEngine.__init__` and let per-call `process()`
   `**kwargs` flow into the converter config (mirror the merge pattern in
   `MarkerEngine.process`). Do not hardcode a default mode - pass through so
   Marker's device auto-selection stays intact unless the caller overrides.
2. Verify the hosted API mode vocabulary. If `accurate` is gone, update
   `MarkerEngine` default and `_VALID_MARKER_PARAMS` comment to
   `balanced`/`fast`/`disable_ocr`.
3. README: reflect that Marker runs locally/CPU/free via `marker_local` (not only
   SaaS/paid).
4. (Optional) Add `chunks` to `OutputFormat` and wire it through both adapters -
   only if there is RAG demand.

## Affected Files
- `src/docfold/engines/marker_local_engine.py` - add `mode`, merge per-call kwargs into config
- `src/docfold/engines/marker_engine.py` - verify/fix `mode` default + valid-params comment
- `pyproject.toml` - bump `marker-local` extra to Marker 2 (`marker-pdf>=2`)
- `README.md` - Marker is local/CPU/free, not only SaaS
- `CHANGELOG.md` - record the mode passthrough + dependency bump
- `tests/engines/test_adapters.py` - Marker local: mode passthrough + per-call kwargs reach config

## Test Plan

### Unit / Functional Tests
- [ ] `test_marker_local_mode_in_config` - constructor `mode="fast"` lands in converter config
- [ ] `test_marker_local_per_call_kwargs` - `process(..., mode="balanced")` reaches config (currently dropped)
- [ ] `test_marker_local_no_mode_default` - omitting mode leaves it unset (device auto-select preserved)
- [ ] SaaS `MarkerEngine` mode-param test updated to the verified vocabulary
- [ ] ABC conformance tests still pass for both adapters

### Integration / E2E Tests
- [ ] E2E: real PDF through `marker_local` on CPU with `mode=fast` and `--disable_ocr` (manual, slow, downloads weights)

### Test Commands
```bash
pytest tests/engines/test_adapters.py -k Marker -v
pytest tests/ -m "not slow"
```

## Edge Cases
- Marker 2 auto-picks mode by device; passing an explicit mode must override, and
  passing none must NOT force a mode (leave auto-selection to marker).
- `--disable_ocr` starts no inference server (pure CPU text-layer) - verify the
  Python `config` equivalent is honored.
- SaaS and local mode vocabularies may differ - do not assume they are identical.

## Out of Scope
- Chandra / Surya standalone engines (full-page VLM OCR) - separate proposals.
- `chunks` format wiring unless RAG demand appears.

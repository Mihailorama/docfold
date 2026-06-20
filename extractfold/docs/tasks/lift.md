---
purpose: "Add Lift as the first structured-extraction engine in extractfold"
status: "IN PROGRESS"
priority: "P1"
created: "2026-06-20"
---

# Feature: Lift extraction engine

## Problem
Datalab open-sourced **Lift**, a 9B VLM that extracts schema-conformant JSON
directly from PDFs and images (90.2% on their benchmark vs. 81.5% for
NuExtract). This is *structured-data extraction by JSON Schema* — a different
contract from docfold's *document → Markdown/layout* engines:

- Input is a document **plus a target schema**, not just a document.
- Output is a filled `dict` conforming to the schema, not a `content: str`.
- Enrichments are per-field confidence / provenance, not reading order / tables.
- Quality is judged on field accuracy & schema compliance, not WER/CER.

Forcing this into docfold's `EngineResult.content: str` / `OutputFormat` model
would be a leaky abstraction and would saddle docfold with a permanent
backward-compatibility obligation for a foreign API. Extraction is a large
enough category (Lift, NuExtract, LLM structured outputs, LlamaExtract) to
warrant its own unified-interface project: **extractfold**.

## Proposed Solution
Bootstrap `extractfold` with a clean extraction contract and Lift as the first
engine.

- `ExtractionEngine` ABC: `extract(file_path, schema, **kwargs) -> ExtractionResult`.
- `ExtractionResult`: `data`, `engine_name`, `schema`, `field_confidence`,
  `provenance`, `valid`, `raw`, `metadata`, `pages`, `processing_time_ms`.
- `ExtractionRouter`: hint / env-default / priority-chain / allowed-engines
  selection, with fallback, batch, compare, and introspection — mirroring
  docfold's router so the projects feel like siblings.
- `LiftEngine`: wraps `lift-pdf` (`from lift import extract`,
  `lift.model.InferenceManager`), vLLM (default) and HuggingFace backends,
  `page_range` / `max_output_tokens` passthrough.
- `evaluation.metrics`: `field_accuracy` (flattened leaf comparison with
  normalization) and `schema_compliance` (jsonschema).

## Affected Files
- `src/extractfold/engines/base.py` — contract + `load_schema`
- `src/extractfold/engines/lift_engine.py` — Lift adapter
- `src/extractfold/engines/router.py` — `ExtractionRouter`
- `src/extractfold/evaluation/metrics.py` — quality metrics
- `tests/...` — unit tests for all of the above

## Test Plan

### Unit / Functional Tests
- [x] `load_schema` from dict / JSON string / file / named ref
- [x] `ExtractionResult.to_dict` omits/includes optional enrichments
- [x] `ExtractionEngine` is abstract; default capabilities are all False
- [x] Router: hint, env default, priority, extension filter, fallback, batch, compare
- [x] Lift: metadata, capabilities (vllm=remote / hf=local), unavailable behavior
- [x] Lift: extract maps result, passes page_range/max_output_tokens, errors on None
- [x] `field_accuracy`: exact / partial / missing / extra / normalization / nested

### Integration / E2E Tests
- [ ] Real Lift run against a sample invoice + schema (requires GPU/vLLM server)

### Test Commands
```bash
pytest tests/
pytest tests/ -m "not integration"
```

## Edge Cases
- `lift-pdf` not installed → `is_available()` is False; `extract()` raises a clear install hint.
- Model returns no extraction → raise with the reported error.
- Schema given as a bare name → `{"$ref": name}` for engines with a schema library.

## Out of Scope
- CLI (`extractfold extract ...`) — follow-up.
- Additional engines (NuExtract, LLM structured outputs) — follow-up.
- Per-field provenance population for Lift (pending model output details).

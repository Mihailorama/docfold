---
purpose: "Upgrade the MinerU engine adapter from legacy magic-pdf 0.9 to MinerU 2.x"
status: "IMPLEMENTED"
priority: "P1"
created: "2026-06-27"
---

# Feature: MinerU 2.x Upgrade

## Problem
The `MinerUEngine` adapter is built on the **legacy** `magic-pdf` package (`>=0.9`)
and its old import surface (`magic_pdf.data.dataset.PymuDocDataset`,
`magic_pdf.operators.models.doc_analyze`, `pipe_txt_mode`/`pipe_ocr_mode`, …).

Upstream [opendatalab/MinerU](https://github.com/opendatalab/MinerU) has been
renamed and rewritten as **MinerU 2.x**:

- The PyPI package is now `mineru` (not `magic-pdf`).
- The Python import root is `mineru` (not `magic_pdf`).
- The legacy `PymuDocDataset` / `doc_analyze` / `pipe_*_mode` API is gone.
  The supported programmatic entry point is `mineru.cli.common.do_parse`.
- New backends are available: `pipeline` (CPU-friendly), `vlm` (VLM engine).

So our integration targets a dead API. Installing `docfold[mineru]` today pulls
an unmaintained version. This task updates the adapter to MinerU 2.x while
preserving the public docfold API (engine name `"mineru"`, `process()` signature,
`EngineResult` shape).

## Proposed Solution
Rewrite `mineru_engine.py` around `mineru.cli.common.do_parse`:

1. Lazy-import `do_parse` and `read_fn` from `mineru.cli.common`.
2. In `process()`, read the file via `read_fn`, run `do_parse` in a thread
   executor into a temp `output_dir`, then read back the generated
   `{name}.md` / `{name}_content_list.json`.
3. Output subdirectory depends on backend (mirrors upstream `do_parse`):
   - `pipeline` → `output_dir/{name}/{parse_method}` (parse_method defaults `auto`)
   - `vlm`      → `output_dir/{name}/vlm`
4. Map kwargs: `lang`, `start_page`/`end_page` → `start_page_id`/`end_page_id`,
   `backend`, `parse_method`. Disable bbox-drawing dumps we don't consume.
5. `is_available()` checks `import mineru`.
6. Constructor gains `backend` (default `"pipeline"`) and keeps
   `config_path`/`gpu` for backward compatibility.

Update the dependency extra to `mineru[core]>=2.0` and refresh docs/changelog.

## Affected Files
- `src/docfold/engines/mineru_engine.py` - rewrite adapter for MinerU 2.x API
- `pyproject.toml` - `mineru` extra: `magic-pdf[full]>=0.9` → `mineru[core]>=2.0`
- `tests/engines/test_adapters.py` - update `TestMinerUEngine` to new API/mocks
- `README.md` - note MinerU 2.x; install hint unchanged (`docfold[mineru]`)
- `CHANGELOG.md` - record the breaking dependency upgrade

## Test Plan

### Unit / Functional Tests
- [ ] `test_name` / `test_supported_extensions` unchanged (`mineru`, `{pdf}`)
- [ ] `test_is_available_when_missing` patches `mineru` (not `magic_pdf`)
- [ ] `test_is_available_when_installed` patches `mineru` present → True
- [ ] `test_capabilities` unchanged
- [ ] `test_config_stored` includes new `backend` default `pipeline`
- [ ] `test_process_returns_engine_result` — mocks `do_parse`+`read_fn`, reads
      generated `.md` from the pipeline output dir
- [ ] `test_process_json_output_format` — reads `_content_list.json`
- [ ] `test_process_with_page_range` — `start_page`/`end_page` forwarded as
      `start_page_id`/`end_page_id`
- [ ] `test_process_vlm_backend` — backend=`vlm` reads from `vlm` subdir
- [ ] ABC conformance test still passes

### Integration / E2E Tests
- [ ] E2E: real PDF through `docfold ... --engine mineru` (manual, slow,
      downloads model weights) — verify markdown + JSON outputs

### Test Commands
```bash
pytest tests/engines/test_adapters.py -k MinerU -v
pytest tests/ -m "not slow"
```

## Edge Cases
- MinerU writes multiple files; we only read `.md` and `_content_list.json`.
- `parse_method="auto"` is the directory name for pipeline (upstream does not
  rewrite the subdir to the resolved txt/ocr method when `auto` is passed).
- Missing output file → raise a clear `RuntimeError`.

## Out of Scope
- `hybrid` backend wiring (can be added later).
- Exposing bounding boxes (MinerU provides them in middle.json; not surfaced).
- Server/HTTP (`vlm-http-client`) backend.

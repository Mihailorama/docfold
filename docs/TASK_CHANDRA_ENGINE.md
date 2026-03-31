# Task: Add Chandra OCR 2 Engine to Docfold

## Overview

Add **Chandra OCR 2** (by Datalab) as a new document processing engine in docfold. Chandra 2 is a 5B-parameter Vision Language Model that achieves **85.9% on the olmOCR benchmark** (state of the art), significantly outperforming existing docfold engines like Marker (76.5%) and Mistral OCR (72.0%). It converts images and PDFs to structured Markdown, HTML, or JSON with layout preservation, supports 90+ languages, and excels at handwriting, tables, math, and complex layouts.

Chandra supports two inference backends: **vLLM** (recommended, remote server) and **HuggingFace Transformers** (local). The docfold adapter should support both.

**Research document:** `docs/RESEARCH_CHANDRA_OCR.md`

---

## Files to Create / Modify

### 1. NEW: `src/docfold/engines/chandra_engine.py`

Create the engine adapter implementing `DocumentEngine` ABC.

**Class: `ChandraEngine`**

- **Constructor parameters:**
  - `method: str = "vllm"` — Inference backend (`"vllm"` or `"hf"`)
  - `model: str = "datalab-to/chandra-ocr-2"` — HuggingFace model name
  - `prompt_type: str = "ocr_layout"` — Chandra prompt type (`"ocr_layout"`, etc.)
  - `vllm_url: str = "http://localhost:8000"` — vLLM server URL (only used when `method="vllm"`)
  - `torch_dtype: str = "bfloat16"` — Dtype for HF inference
  - `device_map: str = "auto"` — Device map for HF inference

- **`name` property:** returns `"chandra"`

- **`supported_extensions` property:** returns `{"pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp"}`

- **`capabilities` property:** returns:
  ```python
  EngineCapabilities(
      table_structure=True,
      heading_detection=True,
      reading_order=True,
  )
  ```

- **`is_available()` method:**
  - For `method="vllm"`: check `import chandra` succeeds
  - For `method="hf"`: check `import transformers, torch, chandra` succeed
  - No model loading or network calls

- **`process()` method:**
  1. Convert input file to PIL Image (per page for PDFs)
  2. Build `BatchInputItem(image=img, prompt_type=self._prompt_type)`
  3. For `method="vllm"`: use `InferenceManager(method="vllm")` + `manager.generate(batch)`
  4. For `method="hf"`: lazy-load model, use `generate_hf(batch, model)`
  5. Parse output with `parse_markdown(result.raw)` for Markdown format
  6. Return `EngineResult` with:
     - `content`: parsed markdown/HTML/JSON string
     - `format`: `OutputFormat.MARKDOWN` (default)
     - `engine_name`: `"chandra"`
     - `metadata`: `{"model": self._model, "method": self._method}`
     - `processing_time_ms`: measured wall-clock time

- **No model loading at:**
  - Module import time
  - Engine construction time
  - `is_available()` check
  - Router registration time

---

### 2. MODIFY: `src/docfold/engines/router.py`

- Add `"chandra"` to `_EXTENSION_PRIORITY` for image and PDF extensions. Given its SOTA accuracy, place it high in priority for scanned/image documents:
  - `"pdf"`: insert after `"mineru"` (or early in list, given superior benchmark scores)
  - `"png"`, `"jpg"`, `"jpeg"`, `"tiff"`, `"bmp"`, `"webp"`: add to image priority lists

- Add `"chandra"` to `_DEFAULT_FALLBACK` list

---

### 3. MODIFY: `src/docfold/cli.py`

- Add Chandra registration block in `_build_router()`:
  ```python
  try:
      from docfold.engines.chandra_engine import ChandraEngine
      router.register(ChandraEngine())
  except Exception:
      pass
  ```

---

### 4. MODIFY: `pyproject.toml`

- Add optional dependency group:
  ```toml
  chandra = [
      "chandra-ocr>=0.1",
  ]
  ```
  - The `chandra-ocr` package already manages its own torch/transformers/vllm dependencies
  - For HF-only usage, users can install `chandra-ocr[hf]` separately

- Add `chandra` to the `all` extra

---

### 5. MODIFY: `tests/engines/test_adapters.py`

Add `TestChandraEngine` class following the existing test pattern:

- `test_name()` — assert `name == "chandra"`
- `test_supported_extensions()` — assert key extensions present (`pdf`, `png`, `jpg`)
- `test_is_available_when_missing()` — mock `sys.modules` to verify `is_available()` returns `False`
- `test_config_stored()` — verify constructor params stored correctly (`_method`, `_model`, `_prompt_type`, `_vllm_url`)
- `test_default_method_is_vllm()` — verify `_method` defaults to `"vllm"`
- `test_capabilities()` — assert `table_structure=True`, `heading_detection=True`, `reading_order=True`

Also update `TestAllEnginesImplementInterface`:
- Add `"docfold.engines.chandra_engine.ChandraEngine"` to the parametrized list

---

### 6. MODIFY: `docs/benchmarks.md`

Add Chandra to the Quick Comparison table:

```markdown
| **Chandra** | Local/VLM | OpenRAIL-M* | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ (90+) | Slow | Free* |
```

Add Engine Profile section for Chandra.

---

## Design Decisions

1. **Dual backend support (vLLM + HF).** vLLM is recommended for production throughput; HF is simpler for development/testing. The `method` parameter switches between them, similar to how Chandra's own CLI works.

2. **vLLM as default.** Production users will run a vLLM server for throughput. The adapter defaults to connecting to `localhost:8000` where `chandra_vllm` runs.

3. **High router priority for scanned documents.** With 85.9% olmOCR score, Chandra should be preferred over lower-scoring engines for scanned PDFs and images. However, for text-based PDFs, faster engines like PyMuPDF should still take priority.

4. **Delegate to chandra-ocr package.** Rather than reimplementing inference logic, depend on the `chandra-ocr` pip package which handles model loading, prompting, and output parsing. This simplifies the adapter and tracks upstream improvements.

5. **Image-first processing.** Chandra is a VLM — it processes images, not text. For PDFs, each page is rendered as an image before being passed to the model. Multi-page PDFs are processed page-by-page.

6. **License awareness.** The OpenRAIL-M model license restricts commercial use above the $2M threshold. Document this clearly in the engine docstring and benchmarks. The code (Apache 2.0) and docfold adapter (MIT) have no restrictions.

---

## Implementation Order

Following TDD (per CLAUDE.md):

1. **Write tests** in `tests/engines/test_adapters.py` for `ChandraEngine`
2. **Create** `src/docfold/engines/chandra_engine.py` — implement to pass tests
3. **Update** `pyproject.toml` — add `chandra` optional dependency
4. **Update** `src/docfold/engines/router.py` — add to priority maps
5. **Update** `src/docfold/cli.py` — register engine
6. **Update** `docs/benchmarks.md` — add Chandra profile
7. **Run** full test suite to verify no regressions

---

## Future Enhancements

- **Datalab API engine** — Add a separate `DatalabEngine` for the hosted API (86.7% olmOCR score, confidence scoring, structured extraction)
- **Confidence scoring integration** — Map Datalab API's per-field confidence scores (1–5) to docfold's quality assessment utilities
- **Batch processing** — Leverage Chandra's native batch inference for multi-page documents
- **Streamlit app integration** — Add Chandra to docfold's comparison UI

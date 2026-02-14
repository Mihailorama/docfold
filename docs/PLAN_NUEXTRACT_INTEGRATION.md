# Plan: Add NuExtract Engine to Docfold

## Overview

Add **NuExtract** (by NuMind) as the 16th document processing engine in docfold. NuExtract is a specialized LLM for **structured information extraction** — it takes unstructured text plus a JSON template and returns populated JSON with extracted fields. This is fundamentally different from the existing engines which focus on *document-to-text* conversion; NuExtract adds a *text-to-structured-JSON* extraction capability.

We will integrate **NuExtract v1.5** (the latest stable text-only version) as the primary target, with the model variant configurable via constructor parameter (supporting v1.0 and v1.5 models). NuExtract v2.0 (multimodal/vision) can be added later as a follow-up.

---

## Files to Create / Modify

### 1. NEW: `src/docfold/engines/nuextract_engine.py`

Create the engine adapter implementing `DocumentEngine` ABC.

**Class: `NuExtractEngine`**

- **Constructor parameters:**
  - `model: str = "numind/NuExtract-1.5"` — HuggingFace model name (also supports `"numind/NuExtract"`, `"numind/NuExtract-large"`, `"numind/NuExtract-1.5-tiny"`)
  - `template: str | dict | None = None` — Default JSON extraction template. If `None`, users must pass `template=` in `process()` kwargs.
  - `device: str | None = None` — Target device (`"cpu"`, `"cuda"`, `"cuda:0"`, etc.). If `None`, **defaults to `"cpu"`**. Users must explicitly opt-in to GPU via `device="cuda"`. No automatic GPU detection — this keeps CPU-only environments working out of the box without requiring CUDA.
  - `max_length: int = 10_000` — Max input token length for tokenizer truncation
  - `max_new_tokens: int = 4_000` — Max generated tokens
  - `batch_size: int = 1` — Batch size for inference
  - `torch_dtype: str | None = None` — Optional dtype string (`"float32"`, `"bfloat16"`, `"float16"`). Defaults to `None` which uses `float32` (safe for CPU). Users on GPU can pass `"bfloat16"` for efficiency.

- **`name` property:** returns `"nuextract"`

- **`supported_extensions` property:** returns `{"pdf", "txt", "html", "md", "csv", "json", "docx", "eml"}`
  - NuExtract operates on text, not raw files. The engine will accept text-based documents whose content can be read as strings. For PDFs or other binary formats, the engine will extract text first (using PyMuPDF if available, or basic file reading) before passing to NuExtract.
  - This broad set allows NuExtract to be used as a post-processing structured extraction step on any text-extractable document.

- **`capabilities` property:** returns `EngineCapabilities(table_structure=True)` — NuExtract can extract structured tabular data via templates with array fields.

- **`is_available()` method:**
  ```python
  try:
      import transformers  # noqa: F401
      import torch  # noqa: F401
      return True
  except ImportError:
      return False
  ```
  Note: This only checks that the libraries are installed. It does NOT load or download any model. Model loading happens lazily on the first `process()` call.

- **`process()` method:**
  1. Accept `template` kwarg (JSON string or dict) — required either via constructor or process() call, raise `ValueError` if neither provided.
  2. Read text content from `file_path`:
     - For `.txt`, `.md`, `.csv`, `.html`, `.eml`: read as UTF-8 text
     - For `.pdf`: use PyMuPDF (`fitz`) if available, otherwise raise informative error
     - For `.json`: read as UTF-8 text
     - For `.docx`: attempt python-docx or raise informative error
  3. Run extraction in thread executor (since model inference is blocking):
     - Load model + tokenizer (lazy, cached on instance — **no model loading at import time or construction time**)
     - Load onto the user-specified `device` (default: CPU)
     - Use the user-specified `torch_dtype` (default: float32 for CPU safety)
     - Format prompt using NuExtract template format:
       ```
       <|input|>
       ### Template:
       {template_json}
       ### Text:
       {text}

       <|output|>
       ```
     - Generate with `torch.no_grad()`, `do_sample=False`, `num_beams=1`
     - Parse output (split on `<|output|>`, take second part)
  4. Return `EngineResult` with:
     - `content`: The extracted JSON string
     - `format`: `OutputFormat.JSON` (always, since NuExtract produces structured JSON)
     - `engine_name`: `"nuextract"`
     - `metadata`: `{"model": self._model, "template": template_used, "device": device_used}`
     - `confidence`: `None` (NuExtract doesn't provide confidence scores)
     - `processing_time_ms`: measured wall-clock time

- **`_do_extract()` private method** (sync, runs in executor):
  - Handles model loading (lazy, first-call caching to `self._loaded_model` and `self._loaded_tokenizer`)
  - Model is loaded to `self._device` (default `"cpu"`)
  - Handles prompt formatting and generation
  - For long documents (>max_length tokens): implement sliding window with accumulated state (NuExtract v1.5 feature) using `### Current:` section in prompt

- **No model downloading or loading at:**
  - Module import time
  - Engine construction time (`__init__`)
  - `is_available()` check
  - Router registration time

---

### 2. MODIFY: `src/docfold/engines/router.py`

- Add `"nuextract"` to `_EXTENSION_PRIORITY` for relevant extensions. Since NuExtract is a structured extraction engine (different use case from OCR/layout), it should be placed **at the end** of priority lists — users will explicitly choose it via `engine_hint="nuextract"` in most cases:
  - `"pdf"`: append `"nuextract"` at end
  - `"txt"`: append `"nuextract"` at end (currently only `"unstructured"`)
  - `"html"`: append `"nuextract"` at end
  - `"csv"`: append `"nuextract"` at end
  - `"md"`: append `"nuextract"` at end

- Add `"nuextract"` to `_DEFAULT_FALLBACK` list (at end)

---

### 3. MODIFY: `src/docfold/cli.py`

- Add NuExtract registration block in `_build_router()`:
  ```python
  try:
      from docfold.engines.nuextract_engine import NuExtractEngine
      router.register(NuExtractEngine())
  except Exception:
      pass
  ```

---

### 4. MODIFY: `pyproject.toml`

- Add optional dependency group:
  ```toml
  nuextract = [
      "transformers>=4.38",
      "torch>=2.0",
      "jsonrepair>=0.28",
  ]
  ```
  - `jsonrepair` is a lightweight library recommended by NuMind for fixing occasional malformed JSON output
  - `torch` is listed without CUDA extras — users on CPU get CPU-only torch by default; GPU users install torch with CUDA separately per PyTorch instructions

- Add `nuextract` to the `all` extra:
  ```toml
  all = [
      "docfold[docling,mineru,...,nuextract,surya,evaluation]",
  ]
  ```

---

### 5. MODIFY: `tests/engines/test_adapters.py`

Add `TestNuExtractEngine` class following the existing test pattern:

- `test_name()` — assert `name == "nuextract"`
- `test_supported_extensions()` — assert key extensions present (`pdf`, `txt`, `html`, `md`, `csv`)
- `test_is_available_when_missing()` — mock `sys.modules` to verify `is_available()` returns `False`
- `test_config_stored()` — verify constructor params stored correctly (`_model`, `_template`, `_max_length`, `_max_new_tokens`, `_batch_size`, `_device`)
- `test_default_device_is_cpu()` — verify `_device` defaults to `"cpu"` (not `"cuda"` or auto-detected)
- `test_capabilities()` — assert `table_structure=True`, others `False`
- `test_template_required()` — verify `ValueError` raised when no template provided
- `test_process_formats_prompt_correctly()` — mock the model to verify the prompt template is correctly assembled

Also update `TestAllEnginesImplementInterface`:
- Add `"docfold.engines.nuextract_engine.NuExtractEngine"` to the parametrized list

---

## Design Decisions

1. **NuExtract v1.5 (text-only) first, v2.0 (vision) later.** v1.5 is stable, MIT-licensed, and doesn't require vision model dependencies (qwen_vl_utils, flash-attn). v2.0 support can be added as a separate engine or as a configuration option in a follow-up.

2. **Template as a first-class parameter.** Unlike other engines that just take a file, NuExtract requires a JSON schema template. This is passed via `process(**kwargs)` as `template=` or set on the constructor as a default.

3. **Output format always JSON.** NuExtract's purpose is structured extraction; it always produces JSON. The `output_format` parameter is accepted but the engine always returns `OutputFormat.JSON`. If the user requests MARKDOWN/TEXT, the JSON is returned as-is (consistent with how other engines handle unsupported formats gracefully).

4. **Low priority in router.** NuExtract serves a different purpose (structured extraction vs. document-to-text), so it should not be auto-selected ahead of OCR/layout engines. Users who want NuExtract will use `engine_hint="nuextract"`.

5. **No model loading by default.** The HuggingFace model is **never** loaded at import, construction, or availability-check time. Loading happens lazily on the first `process()` call only. This ensures:
   - `docfold engines` (CLI listing) stays fast — no model downloads
   - Router registration is instant — no GPU memory allocated
   - `is_available()` only checks `import transformers; import torch` — no network calls
   - Users who never invoke NuExtract pay zero cost for having it registered

6. **CPU by default.** The `device` parameter defaults to `"cpu"`, not auto-detected GPU. This is critical because:
   - Many docfold users run on CPU-only machines
   - Auto-detecting CUDA and loading a 3.8B model onto GPU without consent would be surprising
   - GPU users explicitly pass `device="cuda"` (or `NuExtractEngine(device="cuda")`)
   - `torch_dtype` defaults to `None` (float32) which is safe for CPU; GPU users can opt into `"bfloat16"`

7. **Text extraction as prerequisite.** For binary formats (PDF, DOCX), the engine needs text first. It uses lightweight extraction (PyMuPDF for PDF, python-docx for DOCX) as a pre-step. This keeps NuExtract focused on its strength (structured extraction from text).

8. **jsonrepair dependency.** Added as optional dependency to handle occasional malformed JSON from the model (known edge case per NuMind docs).

---

## Implementation Order

1. Create `src/docfold/engines/nuextract_engine.py` — the core engine adapter
2. Update `pyproject.toml` — add `nuextract` optional dependency group and update `all`
3. Update `src/docfold/engines/router.py` — add to priority maps
4. Update `src/docfold/cli.py` — register in `_build_router()`
5. Add tests in `tests/engines/test_adapters.py` — unit tests for the adapter
6. Run existing test suite to verify no regressions

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Remote Marker engine** (`RemoteMarkerEngine`, default name `modal_marker`): Marker on your own GPU endpoint (Modal or any HTTP host) via a small JSON protocol; URL from the argument, `DOCFOLD_REMOTE_MARKER_URL` or `MODAL_MARKER_URL`; retries; GPU and wall time in metadata. Minimal Modal server in `docs/examples/modal_marker_app.py` (DOCFOLD-16).
- **Script-aware OCR routing** (`docfold.utils.script`): `detect_script_hint(text)` (Unicode ranges; RTL or CJK wins at >= 5% of letters), `detect_script_from_image` (Tesseract OSD), `detect_document_script` (text first, OSD on page 1), and `ScriptRouting(rules, default, max_pages)`. `EngineRouter.process(fallback_engines=...)` now also takes a callable, evaluated only when the primary attempt fails; it may return `(engines, info)` and `info` (e.g. `script_hint`) is recorded on the primary `fallback_chain` entry (DOCFOLD-12).
- **Injectable LLM caller for vision steps**: `VLMOCREngine(preset, acompletion=...)` sends pages through the caller's async LLM gateway (no base URL needed) and `process(..., model=...)` sets the model per call. New `docfold.vision.caption_images(images, models, acompletion=...)`: one batched vision call that describes extracted images (logos, stamps, charts, scanned tables), names each image in the request, splits the answer per image, and walks an ordered model fallback chain (DOCFOLD-17).
- **Page images** (`docfold.render.render_pages`, extra `[render]`): yields `(page_number, image_bytes)` lazily for PDFs, images and office files (LibreOffice). Page subset as `"1-3,7"` or a list, `dpi`, `image_format` `png` / `jpeg` / `webp` with `quality`; jpeg goes through Pillow, whose encoder is about 5x faster than PNG (DOCFOLD-14).
- **Quality-gated fallback**: `EngineRouter.process(quality_gate=..., fallback_engines=[...])` retries on poor output, not only on exceptions, and accepts a fallback when it passes the gate with more text than earlier attempts. `docfold.utils.default_quality_gate` checks chars per page, base64 image ratio, confidence, gibberish and image-only pages under a text layer; `strip_base64_images` / `base64_ratio` helpers. Every result from `EngineRouter.process` carries `fallback_chain`, one record per attempt (`engine`, `chars`, `confidence`, `processing_time_ms`, `selected`, `role`, `skip_reason` / `error`) (DOCFOLD-11).
- **Spreadsheet engine** (`spreadsheet`, extra `[spreadsheet]`): xlsx/xlsm via openpyxl, csv/tsv via the csv module. Text output is TSV per sheet (`Sheet: <name>` header when several); `metadata["cell_map"]` maps every non-empty cell to `sheet`, A1 `cell`, `tsv_row`, `tsv_col`, `value`; JSON output is records (`[{header: value}]` for CSV, `{sheet: [...]}` for workbooks). `csv_to_records(text)` helper. Added last in the xlsx/csv/tsv priority lists, so default routing is unchanged; pick it with `engine_hint="spreadsheet"` (DOCFOLD-15).
- **Supplement merge**: `EngineRouter.process(supplement_engine="marker")` runs a second engine after the primary result is chosen and grafts its `bounding_boxes`, `images` and `metadata` (e.g. `marker_json`) onto the result while keeping the primary text. Recorded in `fallback_chain` with `role="bbox_supplement"`; failures never fail the call (DOCFOLD-13).

### Fixed

- `MarkerEngine` request headers typed correctly; `requests` and `types-requests` are now in `[test]`, so CI type-checks the Marker client (before, mypy saw `requests` as missing and skipped it).

## [0.9.0] - 2026-11-11

### Added

- **Document splitting** (`docfold.split`): one PDF holding several documents → page range and type per document. `split_document(path, types, classifiers)` runs page classifiers in order: `TextPageClassifier` (titles followed by a number sign and OKUD form codes from the text layer, no model; abstains on scans) and `LLMPageClassifier` (text pages 30 per call, scanned pages one image per call; `models` is an ordered cross-provider fallback chain, HTTP 429 retried before moving on; `acompletion` injectable). Failures return the file as one document. `cut_pages(path, "5-7")` rewrites a PDF to a page range deterministically. New extras `[split]`, `[split-llm]` (DOCFOLD-9).

## [0.8.1] - 2026-11-04

### Changed

- CI: macOS tests run as a separate job that no longer gates the PyPI publish. v0.8.0 was tagged but never published because hosted macOS runners were not acquired; 0.8.1 has the same package contents.

## [0.8.0] - 2026-11-04

### Added

- **OCR-VLM presets over an OpenAI-compatible API** (`vlm_ocr_engine.py`). One adapter sends each page image to `/v1/chat/completions` on a vLLM or SGLang server using the prompt and sampling settings from each model card. Presets: `xiaomi_ocr` (Xiaomi-OCR-0; OTSL tables become HTML), `hunyuan_ocr` (HunyuanOCR-1.5), `lighton_ocr` (LightOnOCR-3-1B), `ovis_ocr2` (OvisOCR2) and `dots_ocr` (dots.ocr; layout JSON becomes Markdown). Each preset is its own engine and is available once `DOCFOLD_<PRESET>_URL` is set. No new dependencies.
- **`minicpm_ocr`, `glm_ocr`, `paddleocr_vl` engines** for OCR models that read layout regions: MiniCPM-OCR 1.0 (through the `minicpmvocr parse` SDK CLI), GLM-OCR (`glmocr` SDK, self-hosted mode) and PaddleOCR-VL-1.6 (`paddleocr.PaddleOCRVL` with a vLLM server). Each is available once `DOCFOLD_<ENGINE>_URL` is set (`minicpm_ocr` also takes `backend` / `DOCFOLD_MINICPM_OCR_BACKEND` for llama.cpp or Ollama). All new engines and presets were checked end to end on real GGUF weights. New extras: `[minicpm-ocr]`, `[glm-ocr]`, `[paddleocr-vl]` (not in `[all]`).
- `MinerUEngine` gains `tier`, `server_url` and `vlm_model` for MinerU 4.x, whose VLM model is MinerU2.5-Pro.

### Changed

- `UnlimitedOCREngine` now defaults to `baidu/Unlimited-OCR-2`; multi-page documents go through `infer_multi` in one request. Pass `model="baidu/Unlimited-OCR"` for v1.

### Fixed

- `mineru` engine on MinerU 4.x: `process()` failed with `No module named 'mineru.cli.common'`. It now uses `mineru.parse`; MinerU 2.x/3.x keep the old path.
- `surya` engine on surya-ocr 0.20+: `surya.foundation` was removed. It now uses Surya 2's `SuryaInferenceManager`; older releases keep the old path.
- `liteparse` engine returned no bounding boxes with the current LiteParse CLI (`@llamaindex/liteparse` 2.x), which emits per-page `text_items` instead of `textItems`. It now reads `text_items` and falls back to `textItems` for older CLIs.

## [0.7.0] - 2026-07-23

### Added

- **MCP server (`docfold-mcp`)** — stdio server on FastMCP (official `mcp` SDK, new optional extra `[mcp]`) with four tools: `parse_document` (file or URL → structured markdown/html/json/text), `extract_tables`, `list_engines`, `classify_document`. Tool definitions are token-budget-tested (< 1000 tokens estimated). Failures come back structured (`{"error", "failures"}`), never garbage posing as content. Install: `pip install "docfold[mcp]"`.
- **`docfold install <client>`** — one-click MCP registration for `claude` / `codex` / `cursor` / `vscode` / `generic`. Invokes the client's own CLI (`claude mcp add …`) when available; for Cursor merges `~/.cursor/mcp.json` in place, preserving existing servers; `generic` prints the standard `mcpServers` JSON.
- **`docfold doctor [--json]`** — health check: version, Python, MCP extra presence, per-engine availability.
- **`docfold update [--check] [--extras …] [--json]`** — self-update via PyPI using the running interpreter's pip (stdlib urllib; core stays dependency-free).
- **`docfold --version`**.
- **Agent onboarding docs + landing** — `docs/install.md` (idempotent agent setup instruction), `docs/llms.txt`, and a GitHub Pages landing (`docs/index.html`) with one-click agent install CTA and a 1200×630 PNG social card.
- **Tag release workflow** — `.github/workflows/tag-release.yml` creates release tags via `workflow_dispatch` (verifies the tag matches `__version__`); CI must then be dispatched manually on the tag.

- **Unlimited-OCR engine adapter** — wraps Baidu's open-weight [`Unlimited-OCR`](https://github.com/baidu/Unlimited-OCR) document-parsing VLM (loaded from HuggingFace via `trust_remote_code`). Builds on DeepSeek-OCR with Reference Sliding Window Attention (R-SWA) for one-shot long-horizon parsing. Supports `gundam` and `base` modes, images, and PDFs (rendered to images via PyMuPDF), emitting Markdown/HTML/JSON. Registered in the router for PDF and image inputs. Install: `pip install docfold[unlimited-ocr]` (requires a CUDA GPU).

### Fixed

- **MarkItDown engine now registered in the CLI** — `_build_router()` in `docfold.cli` was missing the MarkItDown adapter, so `docfold engines` did not list it and `docfold convert -e markitdown` failed with "Unknown engine". The engine is now registered like the other adapters and selectable from the command line.

### Changed

- **Single-source version** — `pyproject.toml` now reads the version from `src/docfold/__init__.py` via hatch dynamic versioning (fixes the 0.6.13 vs 0.6.0 drift between package metadata and `__version__`).
- **MinerU engine upgraded to MinerU 2.x** — the adapter now targets the current
  [`mineru`](https://github.com/opendatalab/MinerU) package (formerly `magic-pdf`)
  via its supported `mineru.cli.common.do_parse` API. The dependency extra changed
  from `magic-pdf[full]>=0.9` to `mineru[core]>=2.0`. `MinerUEngine` gains
  `backend` (`pipeline` default, or `vlm`) and `parse_method` constructor options;
  the public engine name (`mineru`), `process()` signature, and `EngineResult`
  shape are unchanged. **Breaking for installs:** reinstall with
  `pip install -U docfold[mineru]` to pull `mineru` 2.x.

### Added (pre-0.7.0, previously unreleased)

- **MarkItDown engine adapter** — wraps Microsoft's [`markitdown`](https://github.com/microsoft/markitdown) pure-Python library that converts Office files, PDFs, HTML, images, CSV/JSON/XML, ePub, audio, and ZIP archives into LLM-friendly Markdown. Added to the `benchmark.py` harness alongside the other local engines. Install: `pip install docfold[markitdown]`.
- **Non-PDF benchmark fixtures** — `benchmark.py` now also generates synthetic DOCX (built with stdlib `zipfile` + minimal Office Open XML, no extra deps), HTML, and CSV documents, and filters engines per-doc by `supported_extensions` so PyMuPDF / OCR engines no longer log spurious errors on Office or web fixtures.
- **OpenDataLoader PDF engine adapter** — wraps the Java-based [`opendataloader-pdf`](https://github.com/opendataloader-project/opendataloader-pdf) tool (via its bundled-JAR Python wheel). Local, deterministic extraction with typed structural elements (heading, paragraph, table, list, header, footer) and per-element bounding boxes. Install: `pip install docfold[opendataloader]` (also requires Java 11+).
- **Multi-script benchmark coverage** — `benchmark.py` now generates Arabic (RTL + shaping), Hebrew (RTL, no shaping), and Simplified Chinese (CJK) synthetic PDFs alongside the existing English docs. Fonts are bundled under `tests/fixtures/fonts/` (OFL-1.1, subsetted where relevant) so the benchmark is reproducible without system font packages.

## [0.6.0] - 2026-02-20

### Added

- **EasyOCR engine adapter** — local OCR with 80+ languages, PyTorch-based, confidence scores. Install: `pip install docfold[easyocr]`

## [0.5.1] - 2026-02-12

### Fixed

- `__version__` in package `__init__.py` was stuck at `0.1.0` — now synced with pyproject.toml

## [0.5.0] - 2026-02-12

### Added

- **`docfold.utils` package** — optional smart routing utilities for consumers:
  - `pre_analyze(file_path)` — lightweight file classification (~50ms): detects `pdf_text` / `pdf_scanned` / `image` / `office` / `html` / `unknown`, page count, text layer presence, optional language detection
  - `quality_ok(result)` — quality assessment for `EngineResult`: minimum text length, OCR confidence threshold, gibberish ratio check
  - `QualityThresholds` — configurable via dataclass or env vars (`DOCFOLD_QUALITY_*`)
  - `gibberish_ratio(text)` — detect OCR garbage (control chars, box-drawing elements)
- **Tesseract confidence scores** — engine now populates `confidence` field using word-level `image_to_data()` averaging (normalized 0–100 → 0–1)
- Tesseract `EngineCapabilities(confidence=True)` declaration
- 50 new tests (175 → 225 total)

## [0.4.0] - 2026-02-12

### Added

- **2 local engine adapters** (total: 15 engines):
  - Nougat (Meta) — academic document understanding, LaTeX formula output, PDF-only
  - Surya (Vik Paruchuri) — multilingual OCR + layout analysis with bounding boxes, confidence scores, and table structure for PDFs and images
- Nougat and Surya added to router extension priority chains (PDF, images, default fallback)
- New optional dependencies: `docfold[nougat]` and `docfold[surya]`

## [0.3.0] - 2026-02-11

### Added

- **3 cloud engine adapters** (total: 13 engines):
  - AWS Textract — enterprise form/table extraction with bounding boxes and confidence scores
  - Google Document AI — GCP-native processing with specialized processors
  - Azure Document Intelligence — widest cloud format support (PDF, images, DOCX, XLSX, PPTX, HTML)
- **`EngineCapabilities` declaration** — each engine declares what enrichments it can populate (bounding boxes, confidence, images, table structure, heading detection, reading order)
- **Extension-aware smart router** — engine selection now uses per-extension priority chains (e.g., `.png` prefers PaddleOCR, `.docx` skips PDF-only engines)
- **User-configurable routing** — `fallback_order` and `allowed_engines` parameters on `EngineRouter`
- **`--engines` CLI flag** — restrict engine selection via `docfold convert file.pdf --engines docling,pymupdf`
- **Feature Coverage Matrix** in `docs/benchmarks.md` — per-engine capability comparison
- Capabilities columns (BBox, Conf, Tbl, Img) in `docfold engines` CLI output

### Changed

- Router `select()` uses extension-based priority map instead of static fallback chain
- README comparison table now includes BBox and Conf columns
- `docfold engines` output includes capability indicators

## [0.2.0] - 2026-02-11

### Added

- **6 new engine adapters** (total: 10 engines):
  - PaddleOCR — standalone multilingual OCR (80+ languages)
  - Tesseract — standalone open-source OCR (100+ languages)
  - Unstructured — all-in-one document ETL (PDF, Office, email, HTML, ePub)
  - LlamaParse — LLM-powered cloud parsing (LlamaIndex)
  - Mistral OCR — Vision LLM document understanding (Mistral AI)
  - Zerox — model-agnostic Vision LLM OCR (GPT-4o, Claude, Gemini, DeepSeek VL)
- **Engine comparison benchmark** — research-based comparison of 16 document processing engines covering text PDF quality, OCR, tables, formulas, multilingual support, speed, and cost
- **"How to Choose" guide** — decision table for quick engine selection
- **Detailed benchmarks doc** (`docs/benchmarks.md`) — per-engine profiles, format support matrix, hardware requirements, cost breakdown

### Changed

- Split monolithic OCR engine into separate **PaddleOCR** and **Tesseract** adapters
- Updated fallback chain to include all 10 engines
- README restructured — benchmark table and decision guide now at the top

### Removed

- `ocr_engine.py` — replaced by `paddleocr_engine.py` and `tesseract_engine.py`

## [0.1.0] - 2026-02-10

### Added

- Core engine abstraction: `DocumentEngine` base class, `EngineResult` dataclass, `OutputFormat` enum
- `EngineRouter` with automatic engine selection, fallback chain, and environment variable configuration
- Batch processing with `process_batch()` — bounded concurrency via `asyncio.Semaphore`, progress callbacks
- Engine comparison via `router.compare()` — run the same document through multiple engines
- **Engine adapters:**
  - Docling (MIT) — PDF, DOCX, PPTX, XLSX, HTML, images, audio
  - MinerU / PDF-Extract-Kit (AGPL-3.0) — PDF (placeholder, requires GPU)
  - Marker API (Datalab SaaS) — PDF, Office, images
  - PyMuPDF — fast text extraction for digital PDFs
  - OCR — PaddleOCR + Tesseract fallback for scanned documents
- **Evaluation framework:**
  - Metrics: CER, WER, Table F1, Heading F1, Reading Order (Kendall's tau)
  - `EvaluationRunner` with ground truth dataset discovery and per-engine scoring
- File type detection via `detect_file_type()` with magic-byte fallback
- CLI with `convert`, `engines`, `compare`, `evaluate` subcommands
- 107 unit tests

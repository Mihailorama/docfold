# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **MarkItDown engine now registered in the CLI** — `_build_router()` in `docfold.cli` was missing the MarkItDown adapter, so `docfold engines` did not list it and `docfold convert -e markitdown` failed with "Unknown engine". The engine is now registered like the other adapters and selectable from the command line.

### Changed

- **MinerU engine upgraded to MinerU 2.x** — the adapter now targets the current
  [`mineru`](https://github.com/opendatalab/MinerU) package (formerly `magic-pdf`)
  via its supported `mineru.cli.common.do_parse` API. The dependency extra changed
  from `magic-pdf[full]>=0.9` to `mineru[core]>=2.0`. `MinerUEngine` gains
  `backend` (`pipeline` default, or `vlm`) and `parse_method` constructor options;
  the public engine name (`mineru`), `process()` signature, and `EngineResult`
  shape are unchanged. **Breaking for installs:** reinstall with
  `pip install -U docfold[mineru]` to pull `mineru` 2.x.

### Added

- **Unlimited-OCR engine adapter** — wraps Baidu's open-weight [`Unlimited-OCR`](https://github.com/baidu/Unlimited-OCR) document-parsing VLM (loaded from HuggingFace via `trust_remote_code`). Builds on DeepSeek-OCR with Reference Sliding Window Attention (R-SWA) for one-shot long-horizon parsing. Supports `gundam` and `base` modes, images, and PDFs (rendered to images via PyMuPDF), emitting Markdown/HTML/JSON. Registered in the router for PDF and image inputs. Install: `pip install docfold[unlimited-ocr]` (requires a CUDA GPU).
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

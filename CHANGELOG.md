# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

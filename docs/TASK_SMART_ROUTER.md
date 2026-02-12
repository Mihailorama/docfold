# Task: Optional Smart Routing Utilities for docfold

**Priority**: Medium  
**Affects**: `src/docfold/engines/router.py`, `src/docfold/engines/base.py`, new utility modules  
**Related**: `DatateraApp/docs/DOCFOLD_AI_UTILS_MIGRATION.md` §2.2

---

## Context

docfold is an **independent library** for document processing. ai-utils is just one consumer.
The library must work predictably and conveniently for **any** external user.

**Current behavior is correct for a library:**
- `EngineRouter.select()` picks the first available engine from a priority list → deterministic, predictable.
- `EngineRouter.process()` runs exactly one engine → no surprises.
- Users control what engines are registered, can use `engine_hint`, `allowed_engines`, `fallback_order`.
- `compare()` lets users explicitly run multiple engines for benchmarking.

**This task does NOT change the core behavior.** The `EngineRouter` stays as-is.

## Problem

Some consumers (like ai-utils) want to build **quality-aware routing on top of docfold** — 
try a free engine first, check if the result is good, escalate to a paid engine if not.

This routing logic belongs in the **consumer**, not in docfold. However, docfold can provide
**optional utility building blocks** that make this easier for any consumer:

1. **Pre-analysis**: classify a file (text PDF vs scanned PDF vs image) before choosing an engine.
2. **Quality assessment**: check if an `EngineResult` meets minimum quality thresholds.
3. **Engine metadata**: ensure `confidence` and `capabilities` are correctly reported.

These are **optional utilities** — the consumer is free to use them or implement their own logic.
The `EngineRouter` itself does NOT change behavior.

---

## Requirements

### 1. Pre-Analysis Utility (Optional)

A lightweight utility to classify files **before** the consumer decides which engine to call.
This is NOT wired into `EngineRouter` — it's a standalone function consumers can use.

**New file**: `src/docfold/utils/pre_analysis.py`

```python
@dataclass
class FileAnalysis:
    """Result of file pre-analysis."""
    mime_type: str                      # e.g. "application/pdf"
    extension: str                      # e.g. "pdf"
    file_size_bytes: int
    category: str                       # e.g. "pdf_text", "pdf_scanned", "image", "office", "html"
    page_count: int | None = None       # for PDFs
    has_text_layer: bool | None = None  # for PDFs: True = text-based, False = scanned
    detected_language: str | None = None  # e.g. "en", "ru" (optional, if langdetect is available)

async def pre_analyze(file_path: str) -> FileAnalysis:
    """Classify a file for routing decisions (~50ms target).
    
    This is a standalone utility — NOT coupled to EngineRouter.
    Consumers can use this to decide which engine to request via engine_hint.
    
    For PDFs:
    - Open with pymupdf, try extracting text from first 2 pages.
    - If text length > 100 chars → category = "pdf_text"
    - If text length ≤ 100 → category = "pdf_scanned"
    - Count pages.
    
    For images: category = "image"
    For office docs: category = "office"
    For HTML: category = "html"
    For unknown: category = "unknown"
    """
```

**Design decisions**:
- This is a **standalone utility**, NOT part of `EngineRouter`.
- Consumers call it themselves if they want content-aware routing.
- Must be fast (~50ms). No heavy processing — just MIME detection, text layer check, page count.
- For PDF classification: use `pymupdf` (already a dependency) to extract text from first 2 pages.
- Language detection: optional, only if `langdetect` is installed. Otherwise `None`.

### 2. Quality Assessment Utility (Optional)

A simple quality check for `EngineResult` — consumers can use this to decide 
whether to accept a result or try a different engine.

**New file**: `src/docfold/utils/quality.py`

```python
@dataclass
class QualityThresholds:
    """Configurable thresholds for quality assessment."""
    min_text_length: int = 50           # minimum chars to consider extraction successful
    ocr_confidence_min: float = 0.8     # minimum OCR confidence to accept
    gibberish_ratio_max: float = 0.3    # max ratio of non-printable/non-unicode chars

def quality_ok(result: EngineResult, thresholds: QualityThresholds | None = None) -> bool:
    """Check if an EngineResult meets minimum quality thresholds.
    
    Returns True if ALL of:
    1. result.content is not None and len(result.content.strip()) >= min_text_length
    2. If result.confidence is not None: confidence >= ocr_confidence_min
    3. gibberish_ratio(result.content) <= gibberish_ratio_max
    
    This is a standalone utility — NOT called automatically by EngineRouter.
    Consumers decide when and how to use it.
    """

def gibberish_ratio(text: str) -> float:
    """Calculate the ratio of non-printable / non-standard-unicode characters.
    
    Used to detect OCR garbage (e.g. "⌂☐▒▓░█" or control characters).
    """
```

**Design decisions**:
- This is a **standalone utility**, NOT wired into `EngineRouter.process()`.
- Consumers call `quality_ok(result)` after getting an `EngineResult` and decide what to do.
- No LLM calls, no external APIs — pure local string analysis.
- Thresholds are configurable via `QualityThresholds` dataclass.
- Also readable from env vars (`DOCFOLD_QUALITY_MIN_TEXT_LENGTH`, etc.) as a convenience.

### 3. Engine Metadata Correctness

Ensure that engines correctly report their capabilities and populate the `confidence` field.
This is important for consumers who want to build quality-aware logic.

#### 3.1. Verify `confidence` field population

Engines that perform OCR should populate `EngineResult.confidence`:
- `tesseract` → set `confidence` from Tesseract's word-level confidence average.
- `paddleocr` → set `confidence` from PaddleOCR's detection scores.
- Other engines → `confidence = None` is fine (consumers skip the confidence check).

- [ ] Verify tesseract adapter populates `confidence` field.
- [ ] Verify paddleocr adapter populates `confidence` field.

#### 3.2. Verify `capabilities` declarations

Each engine adapter should correctly declare its `EngineCapabilities`:
- `bounding_boxes: True` for engines that produce bounding box data (marker, surya, paddleocr, tesseract).
- `confidence: True` for engines that produce confidence scores.
- `table_structure: True` for engines with table detection (docling, marker).

- [ ] Audit all engine adapters for correct `capabilities` property.

---

## What Does NOT Change

| Component | Change? | Notes |
|-----------|---------|-------|
| `EngineRouter.select()` | **No** | Still picks first available from priority list |
| `EngineRouter.process()` | **No** | Still runs exactly one engine, deterministic |
| `EngineRouter.process_batch()` | **No** | Unchanged |
| `EngineRouter.compare()` | **No** | Unchanged |
| `EngineRouter.list_engines()` | **No** | Unchanged |
| `_EXTENSION_PRIORITY` maps | **No** | Static priority lists remain as-is |
| Engine selection behavior | **No** | No random iteration, no automatic retries |
| `engine_hint` / `ENGINE_DEFAULT` | **No** | Work exactly as before |
| `allowed_engines` / `fallback_order` | **No** | Work exactly as before |

**The `EngineRouter` is a deterministic, predictable engine selector. It stays that way.**

Consumers who want quality-aware retry logic (like ai-utils) implement it on their side,
using docfold's utilities as building blocks:

```python
# Example: consumer-side tiered routing (NOT in docfold)
analysis = await pre_analyze(file_path)

# Consumer decides which engine to try based on analysis
if analysis.category == "pdf_text":
    result = await router.process(file_path, engine_hint="pymupdf")
elif analysis.category == "pdf_scanned":
    result = await router.process(file_path, engine_hint="tesseract")

# Consumer checks quality and decides whether to retry
if not quality_ok(result):
    result = await router.process(file_path, engine_hint="docling")
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/docfold/utils/__init__.py` | **NEW** — utils package init |
| `src/docfold/utils/pre_analysis.py` | **NEW** — FileAnalysis + pre_analyze() standalone utility |
| `src/docfold/utils/quality.py` | **NEW** — QualityThresholds + quality_ok() standalone utility |
| `src/docfold/engines/router.py` | **NO CHANGES** |
| `src/docfold/engines/base.py` | **NO CHANGES** |
| Engine adapters (tesseract, paddleocr) | **MINOR** — ensure `confidence` field is populated |
| `tests/utils/test_pre_analysis.py` | **NEW** |
| `tests/utils/test_quality.py` | **NEW** |

---

## Tests Checklist

### Pre-Analysis Tests (`tests/utils/test_pre_analysis.py`)
- [ ] Text-based PDF → `category = "pdf_text"`, `has_text_layer = True`
- [ ] Scanned PDF (image-only) → `category = "pdf_scanned"`, `has_text_layer = False`
- [ ] PNG/JPG image → `category = "image"`
- [ ] DOCX file → `category = "office"`
- [ ] HTML file → `category = "html"`
- [ ] Unknown extension → `category = "unknown"`
- [ ] Page count is correct for multi-page PDF
- [ ] Performance: completes in < 200ms for a 10-page PDF
- [ ] Works without langdetect installed (detected_language = None)

### Quality Assessment Tests (`tests/utils/test_quality.py`)
- [ ] Empty content → `quality_ok() = False`
- [ ] Short content (< 50 chars) → `quality_ok() = False`
- [ ] Normal content (500 chars, no confidence) → `quality_ok() = True`
- [ ] Low confidence (0.3) → `quality_ok() = False`
- [ ] High confidence (0.9) → `quality_ok() = True`
- [ ] No confidence field (None) → confidence check skipped, passes if other checks pass
- [ ] High gibberish ratio (0.5) → `quality_ok() = False`
- [ ] Custom thresholds override defaults
- [ ] Env var thresholds are read correctly

### Engine Metadata Tests
- [ ] tesseract adapter: `confidence` field is populated in EngineResult
- [ ] paddleocr adapter: `confidence` field is populated in EngineResult
- [ ] All adapters: `capabilities` property correctly reflects actual features

---

## Non-Goals (Out of Scope)

- Changing `EngineRouter` behavior (no automatic retries, no quality gates inside router)
- Tiered routing logic inside docfold (this is the consumer's responsibility)
- Cloud engine integration specifics (google_docai, azure_docint, textract config)
- VLLM / LLM-based fallback (consumer-layer concern)
- Skew correction / image preprocessing (consumer-layer concern)
- ai-utils-specific tier config (lives in ai-utils DocfoldBridge)

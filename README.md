# Docfold

[![PyPI version](https://img.shields.io/pypi/v/docfold.svg)](https://pypi.org/project/docfold/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/mihailorama/docfold/actions/workflows/ci.yml/badge.svg)](https://github.com/mihailorama/docfold/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-175%20passed-brightgreen.svg)](#)

**Turn any document into structured data.** Unified Python toolkit for document structuring — one interface, 20+ engines, built-in benchmarks, CLI, and an MCP server for AI agents.

Docfold is the open-source extraction engine from [Datatera.ai](https://datatera.ai) — extracted from our commercial enterprise AI data platform and battle-tested in production with enterprise clients across finance, insurance, and mining.

> Read the announcement: [Docfold - open-source document processing toolkit](https://datatera.ai/blog/docfold-open-source)

## Engine Comparison

> Research-based estimates from public benchmarks, documentation, and community reports. See [detailed methodology](docs/benchmarks.md). Run your own: `docfold compare your_doc.pdf`

| Engine | docfold | Type | License | Text PDF | Scan/OCR | Tables | BBox | Conf | Speed | Cost |
|--------|:-------:|------|---------|:--------:|:--------:|:------:|:----:|:----:|-------|------|
| [**Docling**](https://github.com/docling-project/docling) | ✅ | Local | MIT | ★★★ | ★★☆ | ★★★ | ✅ | — | Medium | Free |
| [**MinerU**](https://github.com/opendatalab/MinerU) | ✅ | Local | AGPL | ★★★ | ★★★ | ★★★ | — | — | Slow | Free |
| [**Marker**](https://www.datalab.to/) | ✅ | SaaS | Paid | ★★★ | ★★★ | ★★★ | ✅ | — | Fast | $$ |
| [**PyMuPDF**](https://pymupdf.readthedocs.io/) | ✅ | Local | AGPL | ★★★ | ☆☆☆ | ★☆☆ | — | — | Ultra | Free |
| [**OpenDataLoader**](https://github.com/opendataloader-project/opendataloader-pdf) | ✅ | Local | Apache | ★★★ | ☆☆☆ | ★★☆ | ✅ | — | Fast | Free |
| [**PaddleOCR**](https://github.com/PaddlePaddle/PaddleOCR) | ✅ | Local | Apache | ★☆☆ | ★★★ | ★★☆ | — | ✅ | Medium | Free |
| [**Tesseract**](https://github.com/tesseract-ocr/tesseract) | ✅ | Local | Apache | ★☆☆ | ★★☆ | ★☆☆ | — | — | Medium | Free |
| [**EasyOCR**](https://github.com/JaidedAI/EasyOCR) | ✅ | Local | Apache | ★☆☆ | ★★★ | ☆☆☆ | — | ✅ | Medium | Free |
| [**Unstructured**](https://github.com/Unstructured-IO/unstructured) | ✅ | Local | Apache | ★★☆ | ★★☆ | ★★☆ | — | — | Medium | Free |
| [**LlamaParse**](https://docs.llamaindex.ai/en/stable/llama_cloud/llama_parse/) | ✅ | SaaS | Paid | ★★★ | ★★★ | ★★★ | — | — | Fast | $$ |
| [**Mistral OCR**](https://docs.mistral.ai/capabilities/document/) | ✅ | SaaS | Paid | ★★★ | ★★★ | ★★★ | — | — | Fast | $$ |
| [**Zerox**](https://github.com/getomni-ai/zerox) | ✅ | VLM | MIT | ★★★ | ★★★ | ★★☆ | — | — | Slow | $$$ |
| [**AWS Textract**](https://aws.amazon.com/textract/) | ✅ | SaaS | Paid | ★★★ | ★★★ | ★★★ | ✅ | ✅ | Fast | $$ |
| [**Google Doc AI**](https://cloud.google.com/document-ai) | ✅ | SaaS | Paid | ★★★ | ★★★ | ★★★ | ✅ | ✅ | Fast | $$ |
| [**Azure Doc Intel**](https://azure.microsoft.com/en-us/products/ai-services/ai-document-intelligence) | ✅ | SaaS | Paid | ★★★ | ★★★ | ★★★ | ✅ | ✅ | Fast | $$ |
| [**Nougat**](https://github.com/facebookresearch/nougat) | ✅ | Local | MIT | ★★★ | ★★☆ | ★★☆ | — | — | Slow | Free |
| [**Surya**](https://github.com/VikParuchuri/surya) | ✅ | Local | GPL | ★★☆ | ★★★ | ★★☆ | ✅ | ✅ | Medium | Free |
| [**Unlimited-OCR**](https://github.com/baidu/Unlimited-OCR) | ✅ | Local/VLM | MIT | ★★★ | ★★★ | ★★★ | — | — | Slow | Free |
| [**MarkItDown**](https://github.com/microsoft/markitdown) | ✅ | Local | MIT | ★★☆ | ★☆☆ | ★★☆ | — | — | Fast | Free |

**★★★** Excellent **★★☆** Good **★☆☆** Basic **☆☆☆** Not supported — **$$** ~$1-3/1K pages **$$$** ~$5-15/1K pages — **BBox** Bounding boxes — **Conf** Confidence scores

> [Full engine profiles, format matrix, hardware requirements, and cost breakdown →](docs/benchmarks.md)

## How to Choose

| Your situation | Recommended engine |
|---|---|
| Digital PDF, speed is critical | **PyMuPDF** — zero deps, ~1000 pages/sec |
| Scanned documents, need OCR | **PaddleOCR** (80+ langs), **EasyOCR** (PyTorch), or **Tesseract** (100+ langs) |
| Complex layouts + tables | **Docling** or **MinerU** (free), **LlamaParse** (paid) |
| Academic papers + math formulas | **MinerU** or **Nougat** (free), **Mistral OCR** (paid) |
| Best quality, budget available | **Mistral OCR** or **LlamaParse** |
| Use any Vision LLM (GPT-4o, Claude, etc.) | **Zerox** — model-agnostic |
| Self-hosted, all-in-one ETL | **Unstructured** with hi_res strategy |
| Diverse file types (not just PDF) | **Docling** or **Unstructured** |
| Need bounding boxes + confidence | **Textract**, **Google DocAI**, or **Azure DocInt** |
| Office files (DOCX/PPTX/XLSX) | **Docling**, **Marker**, **Unstructured**, or **Azure DocInt** |
| AWS/GCP/Azure native pipeline | **Textract** / **Google DocAI** / **Azure DocInt** |

## Why Docfold?

Every engine has trade-offs. Docfold lets you switch between them with one line:

| Challenge | Without Docfold | With Docfold |
|-----------|----------------|--------------|
| Try a new engine | Rewrite your pipeline | Change one string: `engine_hint="docling"` |
| Compare quality | Manual side-by-side | `router.compare("doc.pdf")` — one line |
| Batch 1000 files | Build your own concurrency | `router.process_batch(files, concurrency=5)` |
| Measure accuracy | Write custom metrics | Built-in CER, WER, Table F1, Reading Order |
| Switch engines later | Major refactor | Zero code changes — same `EngineResult` |

```python
from docfold import EngineRouter
from docfold.engines.docling_engine import DoclingEngine
from docfold.engines.pymupdf_engine import PyMuPDFEngine

router = EngineRouter([DoclingEngine(), PyMuPDFEngine()])

# Auto-select the best available engine
result = await router.process("invoice.pdf")
print(result.content)       # Markdown output
print(result.engine_name)   # Which engine was used
print(result.processing_time_ms)

# Compare all engines on the same document
results = await router.compare("invoice.pdf")
for name, res in results.items():
    print(f"{name}: {len(res.content)} chars in {res.processing_time_ms}ms")
```

## Supported Engines

| Engine | Type | License | Formats | GPU | Install |
|--------|------|---------|---------|-----|---------|
| [**Docling**](https://github.com/docling-project/docling) | Local | MIT | PDF, DOCX, PPTX, XLSX, HTML, images | No | `pip install docfold[docling]` |
| [**MinerU**](https://github.com/opendatalab/MinerU) | Local | AGPL-3.0 | PDF | Recommended | `pip install docfold[mineru]` |
| [**Marker API**](https://www.datalab.to/) | SaaS | Paid | PDF, Office, images | N/A | `pip install docfold[marker]` |
| [**PyMuPDF**](https://pymupdf.readthedocs.io/) | Local | AGPL-3.0 | PDF | No | `pip install docfold[pymupdf]` |
| [**OpenDataLoader**](https://github.com/opendataloader-project/opendataloader-pdf) | Local | Apache-2.0 | PDF | No (needs Java 11+) | `pip install docfold[opendataloader]` |
| [**PaddleOCR**](https://github.com/PaddlePaddle/PaddleOCR) | Local | Apache-2.0 | Images, scanned PDFs | Optional | `pip install docfold[paddleocr]` |
| [**Tesseract**](https://github.com/tesseract-ocr/tesseract) | Local | Apache-2.0 | Images, scanned PDFs | No | `pip install docfold[tesseract]` |
| [**EasyOCR**](https://github.com/JaidedAI/EasyOCR) | Local | Apache-2.0 | Images, scanned PDFs | Optional | `pip install docfold[easyocr]` |
| [**Unstructured**](https://github.com/Unstructured-IO/unstructured) | Local | Apache-2.0 | PDF, Office, HTML, email, ePub | Optional | `pip install docfold[unstructured]` |
| [**LlamaParse**](https://docs.llamaindex.ai/en/stable/llama_cloud/llama_parse/) | SaaS | Paid | PDF, Office, images | N/A | `pip install docfold[llamaparse]` |
| [**Mistral OCR**](https://docs.mistral.ai/capabilities/document/) | SaaS | Paid | PDF, images | N/A | `pip install docfold[mistral-ocr]` |
| [**Zerox**](https://github.com/getomni-ai/zerox) | VLM | MIT | PDF, images | Depends | `pip install docfold[zerox]` |
| [**AWS Textract**](https://aws.amazon.com/textract/) | SaaS | Paid | PDF, images | N/A | `pip install docfold[textract]` |
| [**Google Doc AI**](https://cloud.google.com/document-ai) | SaaS | Paid | PDF, images | N/A | `pip install docfold[google-docai]` |
| [**Azure Doc Intel**](https://azure.microsoft.com/en-us/products/ai-services/ai-document-intelligence) | SaaS | Paid | PDF, Office, HTML, images | N/A | `pip install docfold[azure-docint]` |
| [**Nougat**](https://github.com/facebookresearch/nougat) | Local | MIT (code) | PDF | Recommended | `pip install docfold[nougat]` |
| [**Surya**](https://github.com/VikParuchuri/surya) | Local | GPL-3.0 | PDF, images | Optional | `pip install docfold[surya]` |
| [**Unlimited-OCR**](https://github.com/baidu/Unlimited-OCR) | Local/VLM | MIT | PDF, images | Required | `pip install docfold[unlimited-ocr]` |
| **OCR VLMs via vLLM/SGLang** — `xiaomi_ocr`, `hunyuan_ocr`, `lighton_ocr`, `ovis_ocr2`, `dots_ocr` | Self-hosted VLM | Per model | PDF, images | On the server | none (`[pymupdf]` for PDFs) |
| [**MarkItDown**](https://github.com/microsoft/markitdown) | Local | MIT | PDF, Office, HTML, images, CSV/JSON/XML, ePub, audio, ZIP | No | `pip install docfold[markitdown]` |
| **Spreadsheet** (openpyxl) — sheet names + `Sheet!A1` cell map, JSON records | Local | MIT | XLSX, XLSM, CSV, TSV | No | `pip install docfold[spreadsheet]` |

### Open OCR VLMs served over an OpenAI-compatible API

Five recent open OCR models are built in as presets of one engine
(`docfold/engines/vlm_ocr_engine.py`). Serve the model with vLLM or SGLang
using the flags from its model card, then set its URL. The preset stays
unavailable until you do:

```bash
vllm serve lightonai/LightOnOCR-3-1B --limit-mm-per-prompt '{"image": 1}'
export DOCFOLD_LIGHTON_OCR_URL=http://localhost:8000/v1
docfold convert scan.pdf --engine lighton_ocr
```

| Preset | Model | License | Notes |
|--------|-------|---------|-------|
| `xiaomi_ocr` | [Xiaomi-OCR-0](https://huggingface.co/xiaomi-research/Xiaomi-OCR-0) | Apache-2.0 | OTSL tables are converted to HTML |
| `hunyuan_ocr` | [HunyuanOCR-1.5](https://huggingface.co/tencent/HunyuanOCR) | Tencent Hunyuan Community | |
| `lighton_ocr` | [LightOnOCR-3-1B](https://huggingface.co/lightonai/LightOnOCR-3-1B) | Apache-2.0 | Image-only prompt |
| `ovis_ocr2` | [OvisOCR2](https://huggingface.co/ATH-MaaS/OvisOCR2) | Apache-2.0 | Card documents offline vLLM only |
| `dots_ocr` | [dots.ocr](https://huggingface.co/dots-studio/dots.ocr) | MIT | Needs vLLM model registration; layout JSON is flattened to Markdown |

Optional `DOCFOLD_<PRESET>_MODEL` (if you used `--served-model-name`) and
`DOCFOLD_<PRESET>_API_KEY`. Chandra OCR 2 already runs over vLLM through the
`chandra` engine.

Models that read regions rather than whole pages run through their own
layout pipeline, with the model on the same kind of server:

| Engine | Model | Install | Server URL env |
|--------|-------|---------|----------------|
| `minicpm_ocr` | [MiniCPM-OCR 1.0](https://huggingface.co/openbmb/MiniCPM-OCR-1.0) (Apache-2.0) | `pip install docfold[minicpm-ocr]` + paddlepaddle | `DOCFOLD_MINICPM_OCR_URL` |
| `glm_ocr` | [GLM-OCR](https://huggingface.co/zai-org/GLM-OCR) (MIT) | `pip install docfold[glm-ocr]` | `DOCFOLD_GLM_OCR_URL` |
| `paddleocr_vl` | [PaddleOCR-VL-1.6](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) (Apache-2.0) | `pip install docfold[paddleocr-vl]` + paddlepaddle | `DOCFOLD_PADDLEOCR_VL_URL` |

For `minicpm_ocr` behind llama-server or Ollama, also set
`DOCFOLD_MINICPM_OCR_BACKEND=llamacpp` (or `ollama`); the SDK default is vLLM.

`mineru` runs MinerU2.5-Pro on MinerU 4.x (`MinerUEngine(tier=..., server_url=...)`),
`surya` runs Surya OCR 2.5 on surya-ocr 0.20+ (`SURYA_INFERENCE_URL` reuses a
server), and `unlimited_ocr` defaults to Unlimited-OCR-2.

> **Adding your own engine?** Implement the `DocumentEngine` interface — see [Adding a Custom Engine](#adding-a-custom-engine) below.

## Installation

```bash
# Core only (no engines — useful for writing custom adapters)
pip install docfold

# With specific engines
pip install docfold[docling]
pip install docfold[docling,pymupdf,tesseract]

# Everything
pip install docfold[all]
```

Requires **Python 3.10+**.

## CLI

```bash
# Convert a document
docfold convert invoice.pdf
docfold convert report.pdf --engine docling --format html --output report.html

# List available engines
docfold engines

# Compare engines on a document
docfold compare invoice.pdf

# Run evaluation benchmark
docfold evaluate tests/evaluation/dataset/ --output report.json

# Health check: version, MCP extra, per-engine availability
docfold doctor
docfold doctor --json

# Register the MCP server in an AI client (see next section)
docfold install claude

# Self-update (or just check): pip upgrade via the running interpreter
docfold update --check
docfold update --extras mcp,docling
```

## MCP Server (for Claude Code, Cursor, agents)

One-click install:

```bash
pip install "docfold[mcp]"
docfold install claude    # Claude Code
docfold install codex     # Codex CLI
docfold install cursor    # Cursor
docfold install vscode    # VS Code
docfold install generic   # print JSON config for any other client
```

Or drop into any client's MCP config manually:

```json
{ "mcpServers": { "docfold": { "command": "docfold-mcp", "args": [] } } }
```

Exposes `parse_document`, `extract_tables`, `list_engines`, `classify_document` tools over stdio — all 4 tool definitions + instructions cost your agent **under 1000 tokens** (budget-tested). Failures come back structured (`{"error", "failures"}`), never garbage posing as content.

**Setting up with an AI agent?** Just tell it:

```
fetch https://docfold.xyz/install.md
```

— a complete, agent-readable setup instruction (install → verify CLI → register MCP). It's idempotent: safe to run on a machine where docfold is already set up.

## How is this different from Docling / Unstructured / MarkItDown?

They're not competitors — **they're engines inside docfold.** Docling, Unstructured, MarkItDown, PyMuPDF, Marker, Tesseract, and 15+ others are all wrapped behind one `DocumentEngine`/`EngineResult` interface. docfold's job is the layer above any single parser:

- **Routing** — classify the file (born-digital PDF? scan? office doc?) and pick the right engine per extension, falling back down the priority chain when an engine fails on a file.
- **Evaluation** — built-in CER/WER/Table-F1 benchmarks so you pick the best engine for *your* corpus, not the one with the best marketing.
- **One interface** — switching parsers is a one-string change, not a pipeline rewrite. The MCP server stays deliberately small: 4 tight tools, no bloat in your agent's context.

If you love one parser, pin it: `engine_hint="docling"`. If you don't want to choose, don't: `router.process(file)` picks for you.

## Splitting a File into Documents

One PDF or scan often holds several documents (an invoice, an act and a UPD; four
acceptance acts and a cost certificate). `docfold.split` returns each document's page
range and type, so you can extract them one by one. Page classifiers run in order and may
abstain: `TextPageClassifier` reads titles and form codes from the text layer with no
model; `LLMPageClassifier` asks a chat model (scans go one page image per call) and takes
an ordered fallback chain of LiteLLM models.

```python
from docfold.split import LLMPageClassifier, TextPageClassifier, cut_pages, split_document

result = await split_document("merged.pdf", ["Invoice", "Act", "UPD"], [
    TextPageClassifier(),
    LLMPageClassifier(models=["anthropic/claude-haiku-5-5", "gemini/gemini-3.8-flash"]),
])
result.to_dict()
# {"pages": 15, "method": "llm", "documents": [{"type": "Invoice", "start": 1, "end": 1, "pages": "1-1"}, ...]}
cut_pages("merged_copy.pdf", "3-4")  # rewrite a copy to one document's pages
```

Install: `pip install "docfold[split-llm]"` (or `[split]` and pass your own `acompletion=`).
A failing classifier never raises: the file comes back as one document (`method="fallback"`).

## Page Images

`render_pages` yields one page image at a time (PDF, images, and office files
through LibreOffice), for vision models or for showing the source next to
bounding boxes:

```python
import base64
from docfold.render import render_pages   # pip install docfold[render]

for page, data in render_pages("report.pdf", "1-3,7", dpi=150, image_format="jpeg", quality=80):
    b64 = base64.b64encode(data).decode()
```

`image_format` is `png`, `jpeg` or `webp`; only the requested pages are rendered.

## Batch Processing

Process hundreds of documents with bounded concurrency and progress tracking:

```python
from docfold import EngineRouter
from docfold.engines.docling_engine import DoclingEngine

router = EngineRouter([DoclingEngine()])

# Simple batch
batch = await router.process_batch(
    ["invoice1.pdf", "invoice2.pdf", "report.docx"],
    concurrency=3,
)
print(f"{batch.succeeded}/{batch.total} succeeded in {batch.total_time_ms}ms")

# With progress callback
def on_progress(*, current, total, file_path, engine_name, status, **_):
    print(f"[{current}/{total}] {status}: {file_path} ({engine_name})")

batch = await router.process_batch(
    file_paths,
    concurrency=5,
    on_progress=on_progress,
)

# Access results
for path, result in batch.results.items():
    print(f"{path}: {len(result.content)} chars")

# Check errors
for path, error in batch.errors.items():
    print(f"FAILED {path}: {error}")
```

## Unified Result Format

Every engine returns the same `EngineResult` dataclass:

```python
@dataclass
class EngineResult:
    content: str              # The extracted text (markdown/html/json/text)
    format: OutputFormat      # markdown | html | json | text
    engine_name: str          # Which engine produced this
    metadata: dict            # Engine-specific metadata
    pages: int | None         # Number of pages processed
    images: dict | None       # Extracted images {filename: base64}
    tables: list | None       # Extracted tables
    bounding_boxes: list | None  # Layout element positions
    confidence: float | None  # Overall confidence [0-1]
    processing_time_ms: int   # Wall-clock time
    fallback_chain: list | None  # Every router attempt (engine, chars, selected, role, ...)
```

## Evaluation Framework

Docfold includes a built-in evaluation harness to objectively compare engines:

```bash
pip install docfold[evaluation]
docfold evaluate path/to/dataset/ --engines docling,pymupdf,marker
```

**Metrics measured:**

| Metric | What it measures | Target |
|--------|------------------|--------|
| CER (Character Error Rate) | Character-level text accuracy | < 0.05 |
| WER (Word Error Rate) | Word-level text accuracy | < 0.10 |
| Table F1 | Table detection and cell content accuracy | > 0.85 |
| Heading F1 | Heading detection precision/recall | > 0.90 |
| Reading Order Score | Correctness of reading order (Kendall's tau) | > 0.90 |

See [docs/evaluation.md](docs/evaluation.md) for the ground truth JSON schema and detailed usage.

## Architecture

```
                        ┌─────────────────────────────┐
                        │       Your Application      │
                        └──────────┬──────────────────┘
                                   │
                        ┌──────────▼──────────────────┐
                        │       EngineRouter          │
                        │  select() / process()       │
                        │  process_batch() / compare() │
                        └──────────┬──────────────────┘
                                   │
     ┌──────────┬───────┬──────────┴──────┬──────────┬──────────┐
     ▼          ▼       ▼                 ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌──────────┐  ┌────────┐ ┌────────┐ ┌──────┐
│Docling │ │ MinerU │ │Unstructd │  │ Marker │ │PyMuPDF │ │ OCR  │
│(local) │ │(local) │ │ (local)  │  │ (SaaS) │ │(local) │ │Paddle│
└────────┘ └────────┘ └──────────┘  └────────┘ └────────┘ │Tess. │
     │          │           │            │          │      └──────┘
     │     ┌────────┐ ┌──────────┐ ┌────────┐      │          │
     │     │Llama   │ │ Mistral  │ │ Zerox  │      │          │
     │     │Parse   │ │  OCR     │ │ (VLM)  │      │          │
     │     │(SaaS)  │ │ (SaaS)  │ │        │      │          │
     │     └────────┘ └──────────┘ └────────┘      │          │
     │          │           │            │          │          │
     │     ┌────────┐ ┌──────────┐ ┌────────┐      │          │
     │     │Textract│ │Google    │ │ Azure  │      │          │
     │     │ (AWS)  │ │DocAI     │ │DocInt  │      │          │
     │     │        │ │ (GCP)    │ │        │      │          │
     │     └────────┘ └──────────┘ └────────┘      │          │
     └──────────┴───────┴─────────────┴─────────────┴──────────┘
                                   │
                          ┌────────▼───────┐
                          │  EngineResult  │
                          │  (unified)     │
                          └────────────────┘
```

## Engine Selection Logic

When no engine is explicitly specified, the router selects one automatically:

1. **Explicit hint** — `engine_hint="docling"` in the call
2. **Environment default** — `ENGINE_DEFAULT=docling` env var
3. **Extension-aware priority** — each file type has its own engine priority chain (e.g., `.png` prefers PaddleOCR, `.pdf` prefers Docling, `.docx` skips PDF-only engines)
4. **User-configurable** — override with `fallback_order` or restrict with `allowed_engines`

```python
# Restrict to specific engines
router = EngineRouter(engines, allowed_engines={"docling", "pymupdf"})

# Custom fallback order
router = EngineRouter(engines, fallback_order=["pymupdf", "docling", "marker"])

# CLI: --engines flag
# docfold convert invoice.pdf --engines docling,pymupdf
```

### Fallback on poor output

By default the router moves on only when an engine raises. Pass a quality gate to
also retry when the output is poor (too little text per page, low confidence,
gibberish, mostly base64 page images, or a text layer that misses scanned pages):

```python
from docfold.utils import default_quality_gate, strip_base64_images

result = await router.process(
    "scan.pdf",
    engine_hint="pymupdf",                        # fast text layer first
    quality_gate=default_quality_gate,            # or gate(result, path) -> reason | None
    fallback_engines=["docling", "marker"],       # retry order
)
for attempt in result.fallback_chain:
    print(attempt["engine"], attempt["chars"], attempt["selected"], attempt.get("skip_reason"))
text = strip_base64_images(result.content)
```

A fallback is accepted when it passes the gate and has more text than earlier
attempts; if none passes, the attempt with the most text is returned.

### Retry chain by script

`fallback_engines` can be a callable evaluated only when the primary attempt
fails. `ScriptRouting` picks the chain by the document's script (text layer
first, Tesseract OSD on page 1 for scans):

```python
from docfold.utils.script import ScriptRouting

routing = ScriptRouting(
    rules={"arabic": ["marker"]},                 # RTL breaks docling
    default=["docling", "docling_serve", "marker"],
    max_pages={"docling_serve": 5},               # drop slow backends for long docs
)
result = await router.process("scan.pdf", engine_hint="pymupdf",
                              quality_gate=default_quality_gate, fallback_engines=routing)
result.fallback_chain[0]["script_hint"]          # "arabic", "cjk", "cyrillic", "latin", "unknown"
```

### Layout from a second engine

`supplement_engine` keeps the winning text and adds another engine's layout
(typed block bounding boxes, image captions, page images, `marker_json`):

```python
result = await router.process(
    "report.pdf", engine_hint="pymupdf", supplement_engine="marker",
)
result.bounding_boxes   # from marker; result.content is still pymupdf's text
```

It runs only when the supplement did not produce the primary result and
supports the file type; a failure is recorded in `fallback_chain`
(`role="bbox_supplement"`) and does not fail the call.

## Adding a Custom Engine

Implement the `DocumentEngine` interface:

```python
from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

class MyEngine(DocumentEngine):
    @property
    def name(self) -> str:
        return "my_engine"

    @property
    def supported_extensions(self) -> set[str]:
        return {"pdf", "docx"}

    def is_available(self) -> bool:
        try:
            import my_library
            return True
        except ImportError:
            return False

    async def process(self, file_path, output_format=OutputFormat.MARKDOWN, **kwargs):
        # Your extraction logic here
        content = extract(file_path)
        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
        )

# Register it
router.register(MyEngine())
```

## Related Projects

Docfold builds on and integrates with these excellent projects:

| Project | Description |
|---------|-------------|
| [Docling](https://github.com/docling-project/docling) | IBM's document conversion toolkit — PDF, DOCX, PPTX, and more |
| [MinerU](https://github.com/opendatalab/MinerU) (2.x) | End-to-end PDF structuring with layout analysis and formula recognition (pipeline + VLM backends) |
| [Marker](https://github.com/VikParuchuri/marker) | High-quality PDF to Markdown converter |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | Fast PDF/XPS/EPUB processing library |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | Multilingual OCR toolkit (80+ languages) |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | Open-source OCR engine (100+ languages) |
| [Unstructured](https://github.com/Unstructured-IO/unstructured) | ETL toolkit for diverse document types |
| [LlamaParse](https://docs.llamaindex.ai/en/stable/llama_cloud/llama_parse/) | LLM-powered document parsing |
| [Mistral OCR](https://docs.mistral.ai/capabilities/document/) | Vision LLM document understanding |
| [Zerox](https://github.com/getomni-ai/zerox) | Model-agnostic Vision LLM OCR |
| [Nougat](https://github.com/facebookresearch/nougat) | Meta's academic PDF to Markdown model |
| [Surya](https://github.com/VikParuchuri/surya) | Multilingual OCR + layout analysis |
| [Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) | Baidu's one-shot long-horizon document-parsing VLM |

### Built by

| Project | Description |
|---------|-------------|
| [Datatera.ai](https://datatera.ai) | AI-powered data transformation and document processing platform |
| [Orquesta AI](https://orquestaai.com) | AI orchestration and agent management platform |
| [AI Agent Labs](https://aiagentlbs.com) | AI agent services and location-based intelligence |

## Development

```bash
git clone https://github.com/mihailorama/docfold.git
cd docfold
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/ tests/
mypy src/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

MIT. See [LICENSE](LICENSE).

> **Note:** Some engine backends have their own licenses (AGPL-3.0 for PyMuPDF and MinerU, GPL-3.0 for Surya, SaaS terms for Marker/LlamaParse/Mistral). Docfold itself is MIT — the engine adapters are optional extras that you install separately.

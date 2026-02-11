# Docfold

[![PyPI version](https://img.shields.io/pypi/v/docfold.svg)](https://pypi.org/project/docfold/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/mihailorama/docfold/actions/workflows/ci.yml/badge.svg)](https://github.com/mihailorama/docfold/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-107%20passed-brightgreen.svg)](#)

**Turn any document into structured data.**

Docfold is a unified Python toolkit for document structuring. It wraps multiple open-source and commercial extraction engines behind a single interface, so you can convert PDFs, images, Office documents, and more into clean Markdown, HTML, or JSON — and objectively compare which engine works best for your documents.

## Why Docfold?

Every document processing engine has trade-offs:

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

# Or pick a specific engine
result = await router.process("invoice.pdf", engine_hint="pymupdf")

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
| [**OCR**](https://github.com/PaddlePaddle/PaddleOCR) | Local | Apache-2.0 | Images, scanned PDFs | Optional | `pip install docfold[ocr]` |

> **Adding your own engine?** Implement the `DocumentEngine` interface — see [Adding a Custom Engine](#adding-a-custom-engine) below.

## Installation

```bash
# Core only (no engines — useful for writing custom adapters)
pip install docfold

# With specific engines
pip install docfold[docling]
pip install docfold[docling,pymupdf]

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
```

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
              ┌────────────┬───────┴───────┬─────────────┐
              ▼            ▼               ▼             ▼
        ┌──────────┐ ┌──────────┐  ┌────────────┐ ┌──────────┐
        │ Docling  │ │ PyMuPDF  │  │ Marker API │ │   OCR    │
        │ (local)  │ │ (local)  │  │  (remote)  │ │ (local)  │
        └──────────┘ └──────────┘  └────────────┘ └──────────┘
              │            │               │             │
              └────────────┴───────┬───────┘─────────────┘
                                   ▼
                          ┌────────────────┐
                          │  EngineResult  │
                          │  (unified)     │
                          └────────────────┘
```

## Engine Selection Logic

When no engine is explicitly specified, the router selects one automatically:

1. **Explicit hint** — `engine_hint="docling"` in the call
2. **Environment default** — `ENGINE_DEFAULT=docling` env var
3. **Fallback chain** — `docling > mineru > marker > pymupdf > ocr`
4. **Extension compatibility** — Filters to engines that support the file type

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
| [MinerU / PDF-Extract-Kit](https://github.com/opendatalab/MinerU) | End-to-end PDF structuring with layout analysis and formula recognition |
| [Marker](https://github.com/VikParuchuri/marker) | High-quality PDF to Markdown converter |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | Fast PDF/XPS/EPUB processing library |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | Multilingual OCR toolkit |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | Open-source OCR engine |
| [Unstructured](https://github.com/Unstructured-IO/unstructured) | ETL toolkit for diverse document types |
| [LlamaParse](https://docs.llamaindex.ai/en/stable/llama_cloud/llama_parse/) | LLM-powered document parsing |
| [Nougat](https://github.com/facebookresearch/nougat) | Meta's academic PDF → Markdown model |
| [GOT-OCR](https://github.com/Ucas-HaoranWei/GOT-OCR2.0) | General OCR Theory — end-to-end OCR with transformers |

### Built by

| Project | Description |
|---------|-------------|
| [Datera](https://datera.ai) | AI-powered data transformation and document processing platform |
| [Orquesta AI](https://orquestaai.com) | AI orchestration and agent management platform |
| [AI Agent LBS](https://aiagentlbs.com) | AI agent services and location-based intelligence |

## Benchmarks

> Benchmarks are a work in progress. We're building a ground truth dataset across document categories (invoices, academic papers, contracts, forms). Contributions welcome!

Once available, benchmarks will cover:

- **Accuracy**: CER, WER, Table F1, Heading F1 per engine per category
- **Speed**: Pages/second, latency P50/P95
- **Resource usage**: Memory, CPU, GPU utilization
- **Format support**: Which engines handle which formats successfully

To run your own benchmarks:

```bash
pip install docfold[all,evaluation]
docfold evaluate your_dataset/ --output benchmark.json
```

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

> **Note:** Some engine backends have their own licenses (AGPL-3.0 for PyMuPDF and MinerU, SaaS terms for Marker API). Docfold itself is MIT — the engine adapters are optional extras that you install separately.

# Document Processing Engine Benchmarks

This guide helps you choose the right document processing engine for your use case. Ratings are research-based estimates compiled from public benchmarks, official documentation, community reports, and our own testing.

> **Disclaimer:** Ratings reflect general tendencies, not absolute scores. Your results will vary based on document quality, language, layout complexity, and hardware. Use `docfold compare your_doc.pdf` to test on your own data.

## Quick Comparison

| Engine | Type | License | Text PDF | Scan/OCR | Tables | Formulas | Multi-lang | Speed | Cost |
|--------|------|---------|----------|----------|--------|----------|------------|-------|------|
| **Docling** | Local | MIT | ★★★ | ★★☆ | ★★★ | ★★☆ | ★★★ | Medium | Free |
| **MinerU** | Local | AGPL-3.0 | ★★★ | ★★★ | ★★★ | ★★★ | ★★☆ | Slow | Free |
| **Marker** | SaaS | Paid | ★★★ | ★★★ | ★★★ | ★★☆ | ★★★ | Fast | ~$1/1K pages |
| **PyMuPDF** | Local | AGPL-3.0 | ★★★ | ☆☆☆ | ★☆☆ | ☆☆☆ | ★★★ | Ultra-fast | Free |
| **PaddleOCR** | Local | Apache-2.0 | ★☆☆ | ★★★ | ★★☆ | ☆☆☆ | ★★★ (80+) | Medium | Free |
| **Tesseract** | Local | Apache-2.0 | ★☆☆ | ★★☆ | ★☆☆ | ☆☆☆ | ★★★ (100+) | Medium | Free |
| **EasyOCR** | Local | Apache-2.0 | ★☆☆ | ★★★ | ☆☆☆ | ☆☆☆ | ★★★ (80+) | Medium | Free |
| **Unstructured** | Local/SaaS | Apache-2.0 | ★★☆ | ★★☆ | ★★☆ | ★☆☆ | ★★☆ | Medium | Free / Paid API |
| **LlamaParse** | SaaS | Paid | ★★★ | ★★★ | ★★★ | ★★★ | ★★☆ | Fast | ~$3/1K pages |
| **Mistral OCR** | SaaS | Paid | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | Fast | ~$1/1K pages |
| **Zerox** | VLM | MIT | ★★★ | ★★★ | ★★☆ | ★★☆ | ★★★ | Slow | VLM API cost |
| **Nougat** | Local | MIT | ★★★ | ★★☆ | ★★☆ | ★★★ | ★☆☆ | Slow | Free |
| **Surya** | Local | GPL-3.0 | ★★☆ | ★★★ | ★★☆ | ★☆☆ | ★★★ (90+) | Medium | Free |
| AWS Textract | SaaS | Paid | ★★★ | ★★★ | ★★★ | ★☆☆ | ★★☆ | Fast | ~$1.50/1K pages |
| Google Document AI | SaaS | Paid | ★★★ | ★★★ | ★★★ | ★★☆ | ★★★ | Fast | ~$1.50/1K pages |
| Azure Document Intelligence | SaaS | Paid | ★★★ | ★★★ | ★★★ | ★★☆ | ★★★ | Fast | ~$1.50/1K pages |

**Rating scale:** ★★★ Excellent | ★★☆ Good | ★☆☆ Basic | ☆☆☆ Not supported

---

## Engine Profiles

### Docling (IBM)

**Best for:** Diverse document types with good structure preservation.

- **Strengths:** Wide format support (PDF, DOCX, PPTX, XLSX, HTML, images, audio). MIT license. Good table detection with TableFormer model. Active development by IBM Research.
- **Weaknesses:** OCR quality on degraded scans trails dedicated OCR engines. Formula support depends on configuration. Heavier install (~2 GB models).
- **GPU:** Not required, but speeds up layout analysis.
- **Install:** `pip install docfold[docling]`
- **Links:** [GitHub](https://github.com/docling-project/docling) | [Paper](https://arxiv.org/abs/2408.09869)

### MinerU / PDF-Extract-Kit (OpenDataLab)

**Best for:** Academic papers, technical documents with formulas and complex layouts.

- **Strengths:** State-of-the-art layout analysis with PDF-Extract-Kit. Excellent formula recognition (LaTeX output). Strong table extraction. Preserves reading order well.
- **Weaknesses:** PDF-only. Slower than most alternatives. Large model downloads (~5 GB). AGPL license may be restrictive for commercial use.
- **GPU:** Strongly recommended (CUDA). CPU mode is very slow.
- **Install:** `pip install docfold[mineru]`
- **Links:** [GitHub](https://github.com/opendatalab/MinerU)

### Marker (Datalab)

**Best for:** High-quality PDF conversion when you need a reliable cloud API.

- **Strengths:** Excellent accuracy across document types. Fast cloud processing. Handles OCR, tables, and formatting well. Optional LLM enhancement. Also available as local library.
- **Weaknesses:** SaaS dependency. Costs money at scale. Requires API key.
- **GPU:** N/A (cloud).
- **Cost:** Free tier available; paid plans from ~$1/1000 pages.
- **Install:** `pip install docfold[marker]`
- **Links:** [Datalab](https://www.datalab.to/) | [GitHub (local)](https://github.com/VikParuchuri/marker)

### PyMuPDF

**Best for:** Fast text extraction from digital (non-scanned) PDFs.

- **Strengths:** Extremely fast — processes thousands of pages per second. Zero external dependencies. Reliable text extraction from well-formed PDFs. Small memory footprint.
- **Weaknesses:** No OCR capability — produces empty output for scanned PDFs. No layout analysis. No table structure recognition. AGPL license.
- **GPU:** Not needed.
- **Install:** `pip install docfold[pymupdf]`
- **Links:** [Docs](https://pymupdf.readthedocs.io/) | [GitHub](https://github.com/pymupdf/PyMuPDF)

### PaddleOCR (Baidu)

**Best for:** Multilingual OCR, especially for CJK (Chinese, Japanese, Korean) documents.

- **Strengths:** 80+ languages with dedicated models. Strong performance on Asian languages. Good text detection and recognition pipeline. Apache license.
- **Weaknesses:** Not a document structuring engine — returns raw OCR text without layout analysis. Heavier install (PaddlePaddle framework). No table structure or heading recognition.
- **GPU:** Optional, speeds up processing ~5x.
- **Install:** `pip install docfold[paddleocr]`
- **Links:** [GitHub](https://github.com/PaddlePaddle/PaddleOCR)

### Tesseract

**Best for:** Basic OCR needs, maximum language coverage, minimal setup.

- **Strengths:** 100+ languages. Well-established, battle-tested. Runs on any platform. Apache license. No Python framework dependencies.
- **Weaknesses:** Lower accuracy than modern deep learning OCR on complex layouts. No table or structure recognition. Requires system-level binary installation. Slower than PaddleOCR on most benchmarks.
- **GPU:** Not supported.
- **Install:** `pip install docfold[tesseract]` + system binary
- **Links:** [GitHub](https://github.com/tesseract-ocr/tesseract)

### EasyOCR (JaidedAI)

**Best for:** Easy-setup OCR with PyTorch, good multilingual support.

- **Strengths:** 80+ languages. Simple API. PyTorch-based — shares GPU with other PyTorch models in your pipeline. Good accuracy on clean documents. Apache license.
- **Weaknesses:** Slower than PaddleOCR on most benchmarks. No table or layout analysis. Large model downloads. Higher memory usage than Tesseract.
- **GPU:** Optional, recommended for speed.
- **Install:** `pip install docfold[easyocr]`
- **Links:** [GitHub](https://github.com/JaidedAI/EasyOCR)

### Unstructured

**Best for:** ETL pipelines that need to handle diverse document types in a single framework.

- **Strengths:** Widest format support (PDF, DOCX, email, HTML, Markdown, RST, CSV, etc.). Multiple processing strategies (fast/hi_res/ocr_only). Chunking and embedding integration. Apache license.
- **Weaknesses:** Jack of all trades — specialized engines often outperform it on specific formats. hi_res strategy requires additional dependencies (detectron2). SaaS API has separate pricing.
- **GPU:** Optional (needed for hi_res layout model).
- **Install:** `pip install docfold[unstructured]`
- **Links:** [GitHub](https://github.com/Unstructured-IO/unstructured) | [Docs](https://docs.unstructured.io/)

### LlamaParse (LlamaIndex)

**Best for:** Complex documents where you need the best possible accuracy and have budget.

- **Strengths:** LLM-powered parsing understands document semantics. Excellent table and layout extraction. Good integration with LlamaIndex RAG pipelines. Handles complex multi-column layouts.
- **Weaknesses:** Cloud-only (no self-hosting). Costs money. Higher latency than rule-based engines. Rate limits apply.
- **Cost:** Free tier: 1000 pages/day. Paid: ~$3/1000 pages.
- **Install:** `pip install docfold[llamaparse]`
- **Links:** [Docs](https://docs.llamaindex.ai/en/stable/llama_cloud/llama_parse/)

### Mistral OCR

**Best for:** High-accuracy document understanding with strong multilingual support.

- **Strengths:** State-of-the-art vision model for document understanding. Excellent on all document types: scanned, digital, tables, formulas. Strong multilingual support including Cyrillic, Arabic, CJK. Fast API response times.
- **Weaknesses:** Cloud API dependency. Costs per token. Newer service — less community tooling.
- **Cost:** ~$1/1000 pages (based on token pricing).
- **Install:** `pip install docfold[mistral-ocr]`
- **Links:** [Docs](https://docs.mistral.ai/capabilities/document/)

### Zerox (Omni)

**Best for:** Using your preferred Vision LLM for document extraction.

- **Strengths:** Model-agnostic — works with GPT-4o, Claude, Gemini, DeepSeek VL, or any OpenAI-compatible vision endpoint. Good quality from modern VLMs. MIT license for the tool itself.
- **Weaknesses:** Slow (renders pages to images, sends to API). Expensive (VLM token costs add up). Quality depends entirely on the chosen model. No local-only option without a local VLM.
- **Cost:** Depends on VLM provider (GPT-4o: ~$5-15/1K pages).
- **Install:** `pip install docfold[zerox]`
- **Links:** [GitHub](https://github.com/getomni-ai/zerox)

### AWS Textract

**Best for:** AWS-native pipelines, enterprise form/receipt processing.

- **Strengths:** Excellent table and form extraction with cell-level confidence. Bounding boxes for every detected element. Reading order detection via LAYOUT feature. Tight AWS integration (S3, Lambda, Step Functions). Pre-built analyzers for invoices, receipts, ID documents.
- **Weaknesses:** AWS-only (no self-hosting). Pay per page. Limited to PDF and images (no Office formats). US-centric language support.
- **GPU:** N/A (cloud).
- **Cost:** ~$1.50/1000 pages (varies by feature).
- **Install:** `pip install docfold[textract]`
- **Credentials:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
- **Links:** [Docs](https://aws.amazon.com/textract/)

### Google Document AI

**Best for:** GCP-native pipelines, diverse document types with specialized processors.

- **Strengths:** Strong OCR and layout analysis. Bounding boxes with normalized coordinates. High confidence scoring. Specialized processors for invoices, receipts, W2s, passports. Widest image format support (including GIF, WebP). Good multilingual coverage.
- **Weaknesses:** GCP-only. Requires processor setup in Google Cloud Console. Pay per page. Setup more complex than other cloud services.
- **GPU:** N/A (cloud).
- **Cost:** ~$1.50/1000 pages (varies by processor type).
- **Install:** `pip install docfold[google-docai]`
- **Credentials:** `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_DOCAI_PROJECT_ID` + `GOOGLE_DOCAI_LOCATION` + `GOOGLE_DOCAI_PROCESSOR_ID`
- **Links:** [Docs](https://cloud.google.com/document-ai)

### Azure Document Intelligence

**Best for:** Azure-native pipelines, enterprise document workflows, Office format processing.

- **Strengths:** Widest format support among cloud services — PDF, images, AND Office documents (DOCX, XLSX, PPTX, HTML) natively. Bounding boxes with polygon coordinates. Multi-level confidence. Strong table and form extraction. Pre-built models for invoices, receipts, business cards, ID documents. Markdown output mode.
- **Weaknesses:** Azure-only. Requires Azure subscription. Pay per page.
- **GPU:** N/A (cloud).
- **Cost:** ~$1.50/1000 pages (varies by model).
- **Install:** `pip install docfold[azure-docint]`
- **Credentials:** `AZURE_DOCINT_ENDPOINT`, `AZURE_DOCINT_KEY`
- **Links:** [Docs](https://azure.microsoft.com/en-us/products/ai-services/ai-document-intelligence)

---

### Nougat (Meta)

**Best for:** Academic papers with heavy math notation.

- **Strengths:** Transformer model (Swin encoder + mBART decoder) trained on arXiv papers. Excellent LaTeX formula output. Preserves document structure as Mathpix Markdown. Heading and table detection built-in. MIT licensed code.
- **Weaknesses:** PDF-only. English-centric (may work on other Latin-based languages). No bounding boxes or confidence scores. Model weights are CC-BY-NC (non-commercial).
- **GPU:** Strongly recommended (CUDA). CPU mode is very slow.
- **Install:** `pip install docfold[nougat]`
- **Links:** [GitHub](https://github.com/facebookresearch/nougat) | [Paper](https://arxiv.org/abs/2308.13418) | [Hugging Face](https://huggingface.co/facebook/nougat-small)

### Surya (Vik Paruchuri)

**Best for:** Multilingual OCR + layout analysis with bounding boxes.

- **Strengths:** 90+ languages. Provides bounding boxes for text lines, layout elements, and table cells. Layout analysis identifies 11 element types (title, section-header, table, picture, etc.). Handles rotated tables. By the same author as Marker.
- **Weaknesses:** GPL-3.0 license may be restrictive for commercial use. Newer project — API may evolve. Requires PyTorch.
- **GPU:** Optional, speeds up processing significantly.
- **Install:** `pip install docfold[surya]`
- **Links:** [GitHub](https://github.com/VikParuchuri/surya)

---

## Feature Coverage Matrix

Capabilities each engine can populate in `EngineResult`:

| Engine | BBox | Confidence | Images | Tables | Headings | Reading Order |
|--------|:----:|:----------:|:------:|:------:|:--------:|:-------------:|
| Docling | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| MinerU | — | — | — | ✅ | ✅ | ✅ |
| Marker | ✅ | — | ✅ | ✅ | ✅ | — |
| PyMuPDF | — | — | — | — | — | — |
| PaddleOCR | — | ✅ | — | — | — | — |
| Tesseract | — | — | — | — | — | — |
| Unstructured | — | — | — | ✅ | ✅ | — |
| LlamaParse | — | — | — | ✅ | ✅ | — |
| Mistral OCR | — | — | — | ✅ | ✅ | — |
| Zerox | — | — | — | — | — | — |
| **Textract** | ✅ | ✅ | — | ✅ | — | ✅ |
| **Google DocAI** | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| **Azure DocInt** | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| **Nougat** | — | — | — | ✅ | ✅ | ✅ |
| **Surya** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

- **BBox** — Bounding box coordinates for text elements
- **Confidence** — Per-element or overall confidence score
- **Images** — Extracted embedded images
- **Tables** — Structured table data (rows, columns, cells)
- **Headings** — Heading detection and hierarchy
- **Reading Order** — Correct reading order for multi-column layouts

> Use `docfold engines` to see which capabilities are available for your installed engines.

---

## Format Support Matrix

| Engine | PDF | DOCX | PPTX | XLSX | HTML | Images | Email | Audio | ePub |
|--------|-----|------|------|------|------|--------|-------|-------|------|
| Docling | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — |
| MinerU | ✅ | — | — | — | — | — | — | — | — |
| Marker | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ |
| PyMuPDF | ✅ | — | — | — | — | — | — | — | — |
| PaddleOCR | ✅* | — | — | — | — | ✅ | — | — | — |
| Tesseract | ✅* | — | — | — | — | ✅ | — | — | — |
| Unstructured | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| LlamaParse | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ |
| Mistral OCR | ✅ | — | — | — | — | ✅ | — | — | — |
| Zerox | ✅ | — | — | — | — | ✅ | — | — | — |
| **Textract** | ✅ | — | — | — | — | ✅ | — | — | — |
| **Google DocAI** | ✅ | — | — | — | — | ✅ | — | — | — |
| **Azure DocInt** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — |
| **Nougat** | ✅ | — | — | — | — | — | — | — | — |
| **Surya** | ✅ | — | — | — | — | ✅ | — | — | — |

*\* PDF pages are rendered to images before OCR.*

---

## Hardware Requirements

| Engine | Min RAM | Recommended RAM | GPU | Disk (models) |
|--------|---------|-----------------|-----|----------------|
| Docling | 4 GB | 8 GB | Optional | ~2 GB |
| MinerU | 8 GB | 16 GB | CUDA 8+ GB | ~5 GB |
| Marker (local) | 4 GB | 8 GB | Optional | ~2 GB |
| PyMuPDF | 512 MB | 1 GB | — | — |
| PaddleOCR | 2 GB | 4 GB | Optional | ~500 MB |
| Tesseract | 512 MB | 1 GB | — | ~100 MB |
| Unstructured (fast) | 2 GB | 4 GB | — | ~500 MB |
| Unstructured (hi_res) | 8 GB | 16 GB | Optional | ~2 GB |
| Nougat | 8 GB | 16 GB | CUDA 8+ GB | ~1.5 GB |
| Surya | 4 GB | 8 GB | Optional | ~1 GB |


*SaaS engines (LlamaParse, Mistral OCR, Zerox, Marker API, Textract, Google DocAI, Azure DocInt) have no local hardware requirements.*

---

## Cost Comparison

| Engine | Model | Cost per 1,000 pages |
|--------|-------|---------------------|
| PyMuPDF | Free | $0 |
| PaddleOCR | Free | $0 |
| Tesseract | Free | $0 |
| Docling | Free | $0 (compute only) |
| Nougat | Free | $0 (compute + GPU) |
| Surya | Free | $0 (compute only) |
| MinerU | Free | $0 (compute + GPU) |
| Unstructured | Free / API | $0 local / ~$10 API |
| Marker API | SaaS | ~$1 |
| Mistral OCR | SaaS | ~$1 (token-based) |
| LlamaParse | SaaS | ~$3 (free: 1K/day) |
| AWS Textract | SaaS | ~$1.50 |
| Google Doc AI | SaaS | ~$1.50 |
| Azure Doc Intel | SaaS | ~$1.50 |
| Zerox (GPT-4o) | SaaS | ~$5-15 |

*Costs are approximate and may vary based on document complexity, pricing changes, and volume discounts.*

---

## Methodology

These ratings are compiled from:

1. **Official documentation** — stated capabilities and supported features
2. **Published benchmarks** — academic papers and blog posts from engine authors
3. **Community reports** — GitHub issues, discussions, and user feedback
4. **Our own testing** — qualitative assessment on a small document set

Ratings are intentionally simplified to three levels (★★★/★★☆/★☆☆) for quick decision-making. For rigorous comparisons, run `docfold evaluate` on your own dataset with ground truth annotations.

### Running Your Own Benchmarks

```bash
# Install docfold with all engines and evaluation tools
pip install docfold[all,evaluation]

# Compare engines on a single document
docfold compare your_document.pdf

# Run full evaluation with ground truth dataset
docfold evaluate path/to/dataset/ --engines docling,pymupdf,marker --output report.json
```

See [evaluation.md](evaluation.md) for the ground truth JSON schema.

---

## Contributing

Found an inaccuracy? Have benchmark data to share? Please open an issue or PR:

- [Report an issue](https://github.com/mihailorama/docfold/issues)
- [Contributing guide](../CONTRIBUTING.md)

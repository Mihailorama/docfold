# Research: Document Segmentation Tools & Models

Splitting a single document (or document stream) into logical sections or sub-documents.

---

## Problem Taxonomy

Document segmentation covers **four distinct sub-problems:**

| Problem | Example | Key Challenge |
|---|---|---|
| **Page Stream Segmentation (PSS)** | PDF with contract + invoice concatenated | Detecting document boundaries |
| **Section segmentation** | Annual report → balance sheet, P&L, cash flow | Finding logical section breaks |
| **Layout analysis** | Detecting headings, tables, paragraphs on a page | Within-page element identification |
| **Page-level classification** | Classifying each page as "invoice" / "contract" / "letter" | Per-page type labeling |

---

## 1. Page Stream Segmentation (Multi-Document PDF Splitting)

**The least mature area in open source.** No production-ready tool exists.

### Academic State-of-the-Art

| Paper | Year | Approach | Result |
|---|---|---|---|
| PSS with CNNs (Wiedemann & Heyer) | 2017 | CNN combining image + text features | >91% acc on Tobacco800 |
| Tab this Folder of Documents | 2022 | ResNet + LayoutLM + 1D convolutions | Multimodal outperforms unimodal |
| OpenPSS Benchmark | 2024 | Standardized benchmark with public datasets | Addresses lack of public PSS benchmarks |
| **LLMs for PSS** (Heidenreich et al.) | 2024 | Fine-tuned Mistral for PSS | **F1 > 0.9**, perfectly segments 80% of streams |

### Open-Source PSS Implementations

**agiagoulas/page-stream-segmentation** — [GitHub](https://github.com/agiagoulas/page-stream-segmentation)
- Multi-modal CNN + BERT; predicts if consecutive pages belong to same document
- HuggingFace model: `agiagoulas/bert-pss`
- Status: research prototype

**uhh-lt/pss-lrev** — [GitHub](https://github.com/uhh-lt/pss-lrev)
- CNN combining textual + visual features
- Status: academic reference implementation

**Unstract PDF Splitter** — [unstract.com](https://unstract.com/blog/pdf-splitter-api-ai-powered-mixed-combined-pdf-splitter/)
- LLM + Vision AI to detect document boundaries; returns labeled individual PDFs
- License: AGPL-3.0 (platform), cloud API for splitter
- Status: commercial with open-source platform

### Practical PSS Approaches

1. **Fine-tune Mistral-7B** on TABME++ dataset (best research result, F1 > 0.9)
2. **Page classification + transition detection** — classify each page with DiT/LayoutLMv3, split when type changes
3. **Visual similarity** — detect visual discontinuities between consecutive pages (header/footer changes, format shifts)

### Key PSS Datasets

| Dataset | Size | Source |
|---|---|---|
| [Tobacco800](https://www.kaggle.com/datasets/patrickaudriaz/tobacco800) | 1,290 pages / 800 docs | Tobacco litigation |
| [TABME++](https://huggingface.co/datasets/rootsautomation/TABMEpp) | Enhanced benchmark | Roots Automation |
| [OpenPSS](https://link.springer.com/chapter/10.1007/978-3-031-72437-4_24) | Two large datasets | Univ. of Amsterdam |

---

## 2. Layout Analysis & Within-Page Segmentation

### DocLayNet (Dataset)

- **Source:** [GitHub: DS4SD/DocLayNet](https://github.com/DS4SD/DocLayNet), [HuggingFace](https://huggingface.co/datasets/docling-project/DocLayNet)
- 80,863 pages from 6 document categories (Finance, Science, Patents, Tenders, Law, Manuals)
- 11 classes: Text, Picture, Caption, Section-header, Footnote, Title, Formula, List-item, Page-footer, Page-header, Table
- License: CDLA-Permissive-1.0
- **The de facto standard** training dataset for layout models

### Docling (IBM) — ~52.7k stars

- **License:** MIT
- Layout analysis via RT-DETR models trained on DocLayNet (78% mAP, 28ms/image on A100)
- Builds **hierarchical document tree** preserving section/subsection relationships
- Two chunkers: HierarchicalChunker (strict section splits) and HybridChunker (token-aware)
- Core model: Granite-Docling-258M
- **Does NOT do PSS** — assumes single logical document input

### Unstructured — ~13.9k stars

- **License:** Apache 2.0
- Detects semantic elements (Title, NarrativeText, ListItem, Table, etc.)
- Chunking strategies: `by_title` (section-aware), `by_page`, `by_similarity` (embedding-based), `basic`
- `by_title` uses detected Title elements as section boundaries
- **Does NOT do PSS** — processes one document at a time

### GROBID — ~3.2k stars

- **License:** Apache 2.0
- Extracts/structures **scholarly documents** from PDF
- Dedicated segmentation model divides into zones (header, body, bibliography, annex) + 68 fine-grained labels
- CRF or BiLSTM-CRF sequence labeling
- **Production-grade** — used by Semantic Scholar, ResearchGate, Internet Archive, CERN
- Optimized for academic papers only

### HURIDOCS PDF Layout Analysis

- **License:** Apache 2.0
- Two model options: VGT (high accuracy, GPU) or LightGBM (fast, CPU ~0.65 sec/page)
- Trained on DocLayNet
- Reading order detection included

### deepdoctection — ~3.1k stars

- **License:** Apache 2.0
- Orchestration framework combining Detectron2, LayoutLM, Tesseract/DocTR
- Build custom layout + classification pipelines

### Aryn Sycamore — ~354 stars

- **License:** Apache 2.0
- Deformable DETR trained on DocLayNet (80K+ documents)
- Claims 6x more accurate chunking vs alternatives

---

## 3. Page-Level Classification

### Key Models on HuggingFace

| Model | Params | RVL-CDIP Acc | Modality | CPU? |
|---|---|---|---|---|
| **DiT-base** (`microsoft/dit-base-finetuned-rvlcdip`) | 86M | ~92.7% | Image only | Yes |
| **DiT-large** (`microsoft/dit-large`) | 304M | Higher | Image only | Slower |
| **LayoutLMv3-base** | 133M | ~95% | Text + Layout + Image | Yes |
| **LayoutLMv3-large** | 368M | ~95%+ | Text + Layout + Image | Slower |
| **Donut** (`naver-clova-ix/donut-base`) | ~200M | ~95% | Image only | Moderate |

### RVL-CDIP Benchmark

- 400,000 images, 16 document classes (Letter, Invoice, Form, Budget, Resume, etc.)
- State-of-the-art: >97% with ensembles
- Standard benchmark for page classification

---

## 4. Text-Based / Topic Segmentation

### textsplit — [GitHub](https://github.com/chschock/textsplit)

- **License:** MIT
- Segments by topic coherence using word embeddings
- Greedy or dynamic programming algorithms
- Very lightweight, CPU-only

### wtpsplit — [GitHub](https://github.com/segment-any-text/wtpsplit)

- **License:** MIT
- Sentence/paragraph segmentation across 85+ languages
- Transformer-based

### LLM-based segmentation

- Fine-tuned Mistral achieves F1 > 0.9 for PSS (Heidenreich 2024)
- Instructor library has a [guide for LLM document segmentation](https://python.useinstructor.com/examples/document_segmentation/)

---

## 5. Financial Report Section Detection

**No dedicated open-source tool exists.** Practical approaches:

1. **XBRL/SEC EDGAR parsing** — US public company filings are already tagged in XBRL; parse directly
2. **Layout analysis + heading detection** — Docling/Unstructured detect section headers ("Balance Sheet", "Cash Flow Statement"), segment at boundaries
3. **LLM/VLM classification** — financial pages have distinctive visual patterns (dense tables vs narrative text)
4. **Fine-tune LayoutLMv3** on custom dataset of financial report pages labeled by section type
5. **Pattern matching** — regex on detected headings ("Consolidated Balance Sheet", "Notes to Financial Statements")

---

## Key Gaps in Open Source

1. **No production-ready PSS tool** — academic research is solid (F1 > 0.9 with fine-tuned LLMs) but implementations are prototype-level
2. **No financial-document-specific segmentation** — GROBID covers scientific papers; nothing equivalent for financial reports
3. **"Layout analysis" ≠ "document segmentation"** — Docling/Unstructured excel at within-page elements but don't address cross-page document boundaries
4. **Annotation tooling is scarce** — building custom PSS datasets requires labeling document boundaries, which few tools support

---

## Comparison Matrix

| Tool | PSS? | Section Detection | Layout Analysis | Page Classification | License | Stars | CPU? |
|---|---|---|---|---|---|---|---|
| **Docling** | No | Yes (hierarchical) | Yes (258M model) | No | MIT | ~52.7k | Yes (slow) |
| **Unstructured** | No | Yes (by_title) | Yes (hi_res mode) | No | Apache 2.0 | ~13.9k | Yes (fast mode) |
| **GROBID** | No | Yes (scholarly) | Yes (CRF/DL) | No | Apache 2.0 | ~3.2k | Yes |
| **deepdoctection** | No | Via pipeline | Yes (Detectron2) | Yes (LayoutLM) | Apache 2.0 | ~3.1k | Depends |
| **DiT-base** | No | No | No | Yes (92.7%) | MIT | N/A | Yes (86M) |
| **LayoutLMv3** | No | No | No | Yes (95%) | MIT | N/A | Yes (133M) |
| **Mistral fine-tuned** | Yes (F1>0.9) | No | No | No | Apache 2.0 | N/A | GPU |
| **BERT-PSS** | Yes (prototype) | No | No | No | N/A | ~15 | Yes |
| **textsplit** | No | Yes (topic-based) | No | No | MIT | ~300 | Yes |

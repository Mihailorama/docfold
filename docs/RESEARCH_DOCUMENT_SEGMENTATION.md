# Research: Document Segmentation Tools & Models

Splitting a single document (or document stream) into logical sections or sub-documents.

---

## Problem Taxonomy

Document segmentation covers **four distinct sub-problems:**

| Problem | Example | Key Challenge |
|---|---|---|
| **Page Stream Segmentation (PSS)** | PDF with contract + invoice concatenated | Detecting document boundaries |
| **Section segmentation** | Annual report → balance sheet, P&L, notes | Finding logical section breaks |
| **Layout analysis** | Detecting headings, tables, paragraphs on a page | Within-page element identification |
| **Page-level classification** | Classifying each page as "invoice" / "contract" / "letter" | Per-page type labeling |

These apply to **any domain** — finance, logistics, medicine, construction, legal, HR, etc.

---

## 1. Page Stream Segmentation (Multi-Document PDF Splitting)

### Academic State-of-the-Art

| Paper | Year | Approach | Result |
|---|---|---|---|
| PSS with CNNs (Wiedemann & Heyer) | 2017 | CNN combining image + text features | >91% acc on Tobacco800 |
| Tab this Folder of Documents | 2022 | ResNet + LayoutLM + 1D convolutions | Multimodal outperforms unimodal |
| OpenPSS Benchmark | 2024 | Standardized benchmark with public datasets | Addresses lack of public PSS benchmarks |
| **LLMs for PSS** (Heidenreich et al.) | 2024 | Fine-tuned Mistral for PSS | **F1 > 0.9**, perfectly segments 80% of streams |

### Open-Source PSS Implementations

**Marker / Datalab API** — [GitHub](https://github.com/datalab-to/marker), [Docs](https://documentation.datalab.to/api-reference/marker)
- **`segmentation_schema` API parameter** — provide JSON with segment names and descriptions, returns page ranges for each detected segment
- Available via Datalab hosted API and Forge UI
- Also supports TOC-driven workflow: extract table of contents → parse into page ranges → process per-section with `--page_range`
- Status: **production-ready** (via Datalab API); local CLI supports `--page_range` but not automatic schema-driven segmentation

**Unstract PDF Splitter** — [unstract.com](https://unstract.com/blog/pdf-splitter-api-ai-powered-mixed-combined-pdf-splitter/)
- LLM + Vision AI to detect document boundaries; returns labeled individual PDFs
- License: AGPL-3.0 (platform), cloud API for splitter
- Status: commercial with open-source platform

**agiagoulas/page-stream-segmentation** — [GitHub](https://github.com/agiagoulas/page-stream-segmentation)
- Multi-modal CNN + BERT; predicts if consecutive pages belong to same document
- HuggingFace model: `agiagoulas/bert-pss`
- Status: research prototype

**uhh-lt/pss-lrev** — [GitHub](https://github.com/uhh-lt/pss-lrev)
- CNN combining textual + visual features
- Status: academic reference implementation

### Practical PSS Approaches

1. **Marker `segmentation_schema`** — provide document type descriptions, get page ranges back (production-ready via API)
2. **Fine-tune Mistral-7B** on TABME++ dataset (best research result, F1 > 0.9)
3. **Page classification + transition detection** — classify each page with DiT/LayoutLMv3, split when type changes
4. **TOC-driven splitting** — extract table of contents, parse section→page mappings, split accordingly
5. **Visual similarity** — detect visual discontinuities between consecutive pages (header/footer changes, format shifts)

### Key PSS Datasets

| Dataset | Size | Source |
|---|---|---|
| [Tobacco800](https://www.kaggle.com/datasets/patrickaudriaz/tobacco800) | 1,290 pages / 800 docs | Tobacco litigation |
| [TABME++](https://huggingface.co/datasets/rootsautomation/TABMEpp) | Enhanced benchmark | Roots Automation |
| [OpenPSS](https://link.springer.com/chapter/10.1007/978-3-031-72437-4_24) | Two large datasets | Univ. of Amsterdam |

---

## 2. Layout Analysis & Section Detection

### Marker (Datalab) — ~29k stars

- **License:** GPL (code), AI Pubs Open Rail-M (weights)
- **Comprehensive multi-level segmentation built in:**

**Layout-level segmentation (automatic in every conversion):**
- Surya's `LayoutPredictor` (modified EfficientViT) classifies every region on every page into 15+ types including `Section-header`, `Table`, `Form`, `Figure`, `Caption`, `Footnote`, etc.
- Determines reading order across multi-column layouts
- `SectionHeaderProcessor` builds heading hierarchy (h1–h6)

**Hierarchical output structure:**
- **JSON output** (`--output_format json`): tree structure with `children` preserving section nesting
- **Chunks output** (`--output_format chunks`): flattened list, each block with explicit `section_hierarchy` field mapping heading levels to titles (e.g., `{"1": "Main Heading", "2": "Subheading"}`)
- **Auto-generated table of contents** from detected headings with `title`, `heading_level`, `page_id`, `polygon`

**Multi-document segmentation (Datalab API):**
- `segmentation_schema` parameter — JSON with segment names/descriptions → returns page ranges per segment
- Designed for "digitally stapled" PDFs (e.g., rental application packet with many sub-documents)

**Key CLI flags:**
| Flag | Description |
|---|---|
| `--output_format json\|chunks\|markdown\|html` | `json` = tree, `chunks` = flat with section_hierarchy |
| `--page_range "0-5"` or `"0,3,5-10"` | Process specific page ranges |
| `--use_llm` | Gemini LLM for enhanced accuracy (table merging, math, forms) |
| `--paginate` | Separate pages with horizontal rules |
| `--debug` | Save layout overlay images + bounding box JSON |

**Five Surya models used:**
| Model | Purpose |
|---|---|
| LayoutPredictor | Region classification (15+ types incl. Section-header) |
| RecognitionPredictor | OCR |
| TableRecPredictor | Table structure recognition |
| DetectionPredictor | Text boundary detection |
| OCRErrorPredictor | Recognition error correction |

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

## Key Gaps in Open Source

1. **PSS is maturing but not fully solved** — Marker's `segmentation_schema` (via API) is the closest to production-ready; academic fine-tuned LLMs show strong results but lack turnkey implementations
2. **No domain-specific segmentation models** — GROBID covers scholarly papers; nothing equivalent for arbitrary business documents (logistics waybills, medical records, construction permits, etc.)
3. **"Layout analysis" ≠ "document segmentation"** — Docling/Unstructured excel at within-page elements but don't address cross-page document boundaries. Marker bridges this gap with its `segmentation_schema` API.
4. **Annotation tooling is scarce** — building custom PSS datasets requires labeling document boundaries, which few tools support

---

## Comparison Matrix

| Tool | PSS? | Section Detection | Layout Analysis | Page Classification | License | Stars | CPU? |
|---|---|---|---|---|---|---|---|
| **Marker** | **Yes** (API) | **Yes** (heading hierarchy) | **Yes** (Surya, 15+ types) | No | GPL / Rail-M | ~29k | GPU preferred |
| **Docling** | No | Yes (hierarchical) | Yes (258M model) | No | MIT | ~52.7k | Yes (slow) |
| **Unstructured** | No | Yes (by_title) | Yes (hi_res mode) | No | Apache 2.0 | ~13.9k | Yes (fast mode) |
| **GROBID** | No | Yes (scholarly) | Yes (CRF/DL) | No | Apache 2.0 | ~3.2k | Yes |
| **deepdoctection** | No | Via pipeline | Yes (Detectron2) | Yes (LayoutLM) | Apache 2.0 | ~3.1k | Depends |
| **Unstract** | **Yes** (API) | No | No | No | AGPL-3.0 | ~4k | Cloud |
| **DiT-base** | No | No | No | Yes (92.7%) | MIT | N/A | Yes (86M) |
| **LayoutLMv3** | No | No | No | Yes (95%) | MIT | N/A | Yes (133M) |
| **Mistral fine-tuned** | Yes (F1>0.9) | No | No | No | Apache 2.0 | N/A | GPU |
| **BERT-PSS** | Yes (prototype) | No | No | No | N/A | ~15 | Yes |
| **textsplit** | No | Yes (topic-based) | No | No | MIT | ~300 | Yes |

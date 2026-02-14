# Research: Open-Source Structured Data Extraction Libraries

A comprehensive survey of libraries and models comparable to NuExtract, organized by category.

---

## Baseline: NuExtract (NuMind)

| Attribute | Details |
|---|---|
| **Source** | [GitHub](https://github.com/numindai/nuextract), [HuggingFace](https://huggingface.co/numind/NuExtract) |
| **Core capability** | Text-to-JSON structured extraction via JSON template |
| **License** | MIT (v1.0, v1.5); v2.0-2B/8B MIT, v2.0-4B non-commercial |
| **Model sizes** | 0.5B (tiny), 3.8B (base), 7B (large) for v1.x; 2B/8B for v2.0 |
| **Resources** | Tiny runs on CPU; larger models benefit from GPU |

---

## Category 1: LLM-Based Structured Extraction Models

### 1.1 LangExtract (Google)

| Attribute | Details |
|---|---|
| **Source** | [GitHub: google/langextract](https://github.com/google/langextract) |
| **What it does** | Extracts structured info with precise source grounding — maps every extraction to exact character offsets |
| **Interface** | Few-shot example-based; uses controlled generation for schema enforcement |
| **License** | Apache 2.0 |
| **Resources** | No model of its own — wraps Gemini or local models via Ollama |
| **Stars** | New (July 2025), growing rapidly |
| **Key diff vs NuExtract** | Character-level source traceability; interactive HTML visualization; optimized for very long documents. Not standalone — depends on external LLM |

### 1.2 GLiNER / GLiNER-2

| Attribute | Details |
|---|---|
| **Source** | [GitHub: urchade/GLiNER](https://github.com/urchade/GLiNER) |
| **What it does** | Zero-shot Named Entity Recognition — extract any entity type without pre-defined lists. GLiNER-2 adds structured JSON parsing |
| **Interface** | Provide entity type labels + text → get matching spans |
| **License** | Apache 2.0 |
| **Model sizes** | 50M–300M (BERT-sized, 140x smaller than NuExtract) |
| **Resources** | Runs on CPU with <150ms latency |
| **Stars** | ~2.5k |
| **Key diff vs NuExtract** | Much smaller/faster. Ideal for flat NER but cannot produce deeply nested JSON. Best for high-throughput entity extraction |

### 1.3 Kor

| Attribute | Details |
|---|---|
| **Source** | [GitHub: eyurtsev/kor](https://github.com/eyurtsev/kor) |
| **What it does** | Schema + examples → prompt → LLM → parsed output. Built on LangChain |
| **License** | MIT |
| **Resources** | No model — wraps any LLM |
| **Stars** | ~1.7k |
| **Key diff vs NuExtract** | Pure orchestration layer. Author now recommends native tool-calling APIs where available |

---

## Category 2: Traditional NER / Information Extraction Frameworks

### 2.1 spaCy

| Attribute | Details |
|---|---|
| **Source** | [GitHub: explosion/spaCy](https://github.com/explosion/spaCy) |
| **What it does** | Industrial-strength NLP: NER, POS tagging, dependency parsing. `spacy-llm` adds LLM integration |
| **License** | MIT |
| **Resources** | CPU-friendly (Cython core), models 15MB–400MB |
| **Stars** | ~33k |
| **Key diff vs NuExtract** | Extremely fast, 70+ language models, production-proven. Limited to pre-defined entity types unless using custom training |

### 2.2 Stanza (Stanford NLP)

| Attribute | Details |
|---|---|
| **Source** | [GitHub: stanfordnlp/stanza](https://github.com/stanfordnlp/stanza) |
| **What it does** | Multilingual NLP pipeline: tokenization, NER, parsing (70+ languages) |
| **License** | Apache 2.0 |
| **Stars** | ~7.5k |
| **Key diff vs NuExtract** | Best multilingual NER coverage. Pre-defined entity types, not schema-driven |

---

## Category 3: Document AI / Form Extraction Models

### 3.1 Donut (Naver/Clova)

| Attribute | Details |
|---|---|
| **Source** | [GitHub: clovaai/donut](https://github.com/clovaai/donut) |
| **What it does** | OCR-free document understanding: document image → structured JSON directly |
| **License** | MIT |
| **Model size** | ~200M parameters |
| **Stars** | ~6k |
| **Key diff vs NuExtract** | Processes images directly without OCR. Ideal for forms/receipts. Requires domain-specific fine-tuning |

### 3.2 LayoutLMv3 (Microsoft)

| Attribute | Details |
|---|---|
| **Source** | [HuggingFace: microsoft/layoutlmv3-base](https://huggingface.co/microsoft/layoutlmv3-base) |
| **What it does** | Multimodal document understanding combining text + layout (bounding boxes) + visual features |
| **License** | Check model card — some restrictions |
| **Model sizes** | 125M (base), 355M (large) |
| **Key diff vs NuExtract** | Provides bounding box locations for every extracted value. Requires OCR preprocessing |

### 3.3 UDOP (Microsoft)

| Attribute | Details |
|---|---|
| **Source** | [HuggingFace: microsoft/udop-large](https://huggingface.co/microsoft/udop-large) |
| **What it does** | Unified text + image + layout for document understanding, QA, classification |
| **License** | MIT |
| **Model size** | 742M |
| **Key diff vs NuExtract** | State-of-the-art on 9 Document AI benchmarks. Combines OCR, layout, and vision |

### 3.4 Pix2Struct (Google)

| Attribute | Details |
|---|---|
| **Source** | [HuggingFace: google/pix2struct-docvqa-base](https://huggingface.co/google/pix2struct-docvqa-base) |
| **What it does** | Purely visual: screenshot → structured text. Pre-trained on web page screenshots |
| **License** | Apache 2.0 |
| **Model sizes** | 282M (base), 1.3B (large) |
| **Key diff vs NuExtract** | Versatile for charts, diagrams, UI screenshots. Purely pixel-based — no OCR needed |

---

## Category 4: Schema-Driven Extraction Tools (LLM Output Enforcement)

### 4.1 Instructor

| Attribute | Details |
|---|---|
| **Source** | [GitHub: 567-labs/instructor](https://github.com/567-labs/instructor) |
| **What it does** | Pydantic-based schema enforcement for any LLM. `response_model` parameter + auto-validation + retries |
| **License** | MIT |
| **Languages** | Python, TypeScript, Go, Ruby, Elixir, Rust |
| **Stars** | ~11k, 3M+ monthly PyPI downloads |
| **Key diff vs NuExtract** | Model-agnostic orchestrator. Re-prompting strategy (send → validate → retry). Complementary: could wrap NuExtract with validation |

### 4.2 Outlines (dottxt)

| Attribute | Details |
|---|---|
| **Source** | [GitHub: dottxt-ai/outlines](https://github.com/dottxt-ai/outlines) |
| **What it does** | Guaranteed structured output via constrained decoding — modifies logits in real-time |
| **License** | Apache 2.0 |
| **Stars** | ~13k |
| **Key diff vs NuExtract** | 100% valid output guaranteed (no retries). Works at token level. Can reduce throughput. Complementary to NuExtract |

### 4.3 Guidance (Microsoft)

| Attribute | Details |
|---|---|
| **Source** | [GitHub: guidance-ai/guidance](https://github.com/guidance-ai/guidance) |
| **What it does** | Constrained decoding with context-free grammars, conditionals, loops. Rust engine (~50μs/token) |
| **License** | MIT |
| **Stars** | ~19k |
| **Key diff vs NuExtract** | Most powerful control-flow for structured generation. `llguidance` engine used inside OpenAI, vLLM, SGLang, llama.cpp. Complementary |

---

## Category 5: Open-Source Document Processing Platforms

### 5.1 IBM Docling

| Attribute | Details |
|---|---|
| **Source** | [GitHub: docling-project/docling](https://github.com/docling-project/docling) |
| **What it does** | Full document conversion: PDF, DOCX, PPTX, XLSX, HTML, images → Markdown/HTML/JSON |
| **License** | MIT |
| **Model** | Granite-Docling-258M |
| **Stars** | ~37k |
| **Key diff vs NuExtract** | Full pipeline for 15+ formats. Complementary: Docling for parsing → NuExtract for extraction |

### 5.2 PaddleOCR

| Attribute | Details |
|---|---|
| **Source** | [GitHub: PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |
| **What it does** | End-to-end OCR + document AI: detection, recognition, layout, tables, KIE, charts |
| **License** | Apache 2.0 |
| **Model sizes** | <100M for core OCR |
| **Stars** | ~50k |
| **Key diff vs NuExtract** | Most comprehensive OCR suite, 100+ languages. Requires PaddlePaddle (not PyTorch) |

### 5.3 Marker (Datalab)

| Attribute | Details |
|---|---|
| **Source** | [GitHub: datalab-to/marker](https://github.com/datalab-to/marker) |
| **What it does** | Document → Markdown + JSON with optional LLM-assisted extraction via JSON Schema |
| **License** | GPL (code), AI Pubs Open Rail-M (weights) |
| **Stars** | ~29k |
| **Key diff vs NuExtract** | Takes document files directly. `--use_llm` mode for schema extraction. More restrictive licensing |

### 5.4 Unstructured.io

| Attribute | Details |
|---|---|
| **Source** | [GitHub: Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured) |
| **What it does** | Document ETL: ingests 25+ types into structured elements for LLM consumption |
| **License** | Apache 2.0 |
| **Stars** | ~14k |
| **Key diff vs NuExtract** | Broadest format support. Document parser/preprocessor, not a field extractor |

### 5.5 deepdoctection

| Attribute | Details |
|---|---|
| **Source** | [GitHub: deepdoctection/deepdoctection](https://github.com/deepdoctection/deepdoctection) |
| **What it does** | Document AI orchestration: layout analysis + OCR + token classification via LayoutLM/LiLT |
| **License** | Apache 2.0 |
| **Stars** | ~3.1k |
| **Key diff vs NuExtract** | Orchestration framework combining multiple models into custom pipelines |

### 5.6 Unstract

| Attribute | Details |
|---|---|
| **Source** | [GitHub: Zipstack/unstract](https://github.com/Zipstack/unstract) |
| **What it does** | No-code LLM ETL platform. Dual-LLM "LLMChallenge" approach for cross-validation |
| **License** | AGPL-3.0 |
| **Stars** | ~4k |
| **Key diff vs NuExtract** | No-code UI, dual-LLM consensus. Enterprise-focused |

---

## Comparison Matrix

| Tool | Category | License | Model Size | CPU? | Stars | Standalone? |
|---|---|---|---|---|---|---|
| **NuExtract** | LLM extraction | MIT | 0.5B–8B | Tiny: yes | N/A | Yes |
| **LangExtract** | LLM extraction | Apache 2.0 | Needs LLM | Via Ollama | New | No |
| **GLiNER** | NER/extraction | Apache 2.0 | 50M–300M | Yes (<150ms) | ~2.5k | Yes |
| **Kor** | LLM extraction | MIT | Needs LLM | Via llama.cpp | ~1.7k | No |
| **spaCy** | NER/NLP | MIT | 15M–400M | Yes | ~33k | Yes |
| **Stanza** | NER/NLP | Apache 2.0 | Varies | GPU preferred | ~7.5k | Yes |
| **Donut** | Document AI | MIT | ~200M | GPU preferred | ~6k | Yes |
| **LayoutLMv3** | Document AI | Check card | 125M–355M | GPU preferred | N/A | Yes |
| **UDOP** | Document AI | MIT | 742M | GPU required | N/A | Yes |
| **Pix2Struct** | Document AI | Apache 2.0 | 282M–1.3B | GPU preferred | N/A | Yes |
| **Instructor** | Schema enforcement | MIT | No model | N/A | ~11k | No |
| **Outlines** | Schema enforcement | Apache 2.0 | No model | N/A | ~13k | No |
| **Guidance** | Schema enforcement | MIT | No model | N/A | ~19k | No |
| **Docling** | Doc platform | MIT | 258M | Yes | ~37k | Yes |
| **PaddleOCR** | Doc platform | Apache 2.0 | <100M | Yes | ~50k | Yes |
| **Marker** | Doc platform | GPL/Rail-M | Varies | GPU preferred | ~29k | Yes |
| **Unstructured** | Doc platform | Apache 2.0 | N/A | Yes (limited) | ~14k | No |
| **deepdoctection** | Doc platform | Apache 2.0 | Varies | GPU preferred | ~3.1k | No |
| **Unstract** | Doc platform | AGPL-3.0 | Needs LLM | Via Ollama | ~4k | No |

---

## Recommended Integration Stack

For a document processing framework like docfold:

1. **Document ingestion & OCR** — Docling (MIT, 37k stars) or PaddleOCR (Apache 2.0, 50k stars)
2. **Structured extraction** — NuExtract (template-based text→JSON) + GLiNER (fast entity-level extraction)
3. **Output validation** — Instructor (Pydantic validation + retries) or Outlines (constrained decoding)
4. **Layout-dependent documents** — LayoutLMv3 or Donut (forms, invoices with spatial layout)

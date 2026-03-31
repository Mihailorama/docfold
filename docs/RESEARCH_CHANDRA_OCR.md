# Research: Chandra OCR 2 — State-of-the-Art Document OCR

A comprehensive analysis of Chandra OCR 2 by Datalab, evaluating it as a candidate engine for docfold.

---

## Overview

| Attribute | Details |
|---|---|
| **Source** | [GitHub](https://github.com/datalab-to/chandra), [HuggingFace](https://huggingface.co/datalab-to/chandra-ocr-2) |
| **Core capability** | Convert images/PDFs to structured Markdown, HTML, or JSON with layout preservation |
| **Model size** | ~5B parameters (4B advertised, BF16) |
| **Architecture** | Vision Language Model based on Qwen 3.5 (Image-Text-to-Text) |
| **Code license** | Apache 2.0 |
| **Model license** | Modified OpenRAIL-M (free for research, personal use, startups <$2M funding/revenue) |
| **Install** | `pip install chandra-ocr` (extras: `[hf]`, `[all]`) |
| **Inference** | vLLM (recommended) or HuggingFace Transformers |
| **Downloads** | ~31K/month on HuggingFace |

---

## Key Capabilities

- **Output formats:** Markdown, HTML, JSON with detailed layout information
- **Handwriting:** Excellent handwriting recognition (cursive, notes, forms)
- **Forms:** Accurate checkbox and filled-field reconstruction
- **Tables:** Strong table extraction and structure preservation
- **Math:** LaTeX formula extraction from printed and handwritten equations
- **Images/diagrams:** Extraction with captions and structured data
- **Languages:** 90+ languages with strong multilingual performance
- **Complex layouts:** Multi-column, headers/footers, nested structures

---

## Benchmark Results

### olmOCR Benchmark (Overall Score %)

| Model | Score |
|---|---|
| **Datalab API** | **86.7** |
| **Chandra 2** | **85.9** |
| dots.ocr 1.5 | 83.9 |
| Chandra 1 | 83.1 |
| olmOCR 2 | 82.4 |
| dots.ocr | 79.1 |
| olmOCR v0.3.0 | 78.5 |
| Marker v1.10.0 | 76.5 |
| Deepseek OCR | 75.4 |
| Mistral OCR | 72.0 |
| GPT-4o | 69.9 |
| Qwen 3 VL 8B | 64.6 |
| Gemini Flash 2 | 63.8 |

### olmOCR Benchmark Breakdown

| Model | ArXiv | Old Scans Math | Tables | Headers/Footers | Overall |
|---|---|---|---|---|---|
| **Chandra 2** | 90.2 | 89.3 | 89.9 | 92.5 | 85.9 |
| Datalab API | 90.4 | 90.2 | 90.7 | 91.6 | 86.7 |
| dots.ocr 1.5 | 85.9 | 85.5 | 90.7 | 94.0 | 83.9 |
| Chandra 1 | 82.2 | 80.3 | 88.0 | 90.8 | 83.1 |
| GPT-4o | 53.5 | 74.5 | 70.0 | 93.8 | 69.9 |
| Gemini Flash 2 | 54.5 | 56.1 | 72.1 | 64.7 | 63.8 |

### Multilingual Benchmark (43 languages)

- **Average:** 77.8% (+12% improvement over Chandra 1)
- **Top performers:** Portuguese (95.2%), German (94.8%), Italian (94.1%), French (93.7%), Swedish (92.8%)
- **90-language eval:** Chandra 2 averages 72.7% vs Gemini 2.5 Flash at 60.8%

### Chandra 2 vs Existing docfold Engines

| Criterion | Chandra 2 | Marker | Mistral OCR | Surya | Nougat |
|---|---|---|---|---|---|
| **olmOCR Score** | 85.9% | 76.5% | 72.0% | N/A | N/A |
| **Multi-lang** | 90+ langs | Good | Good | 90+ langs | English-centric |
| **Tables** | ★★★ | ★★★ | ★★★ | ★★☆ | ★★☆ |
| **Math/Formulas** | ★★★ | ★★☆ | ★★★ | ★☆☆ | ★★★ |
| **Handwriting** | ★★★ | ★☆☆ | ★★☆ | ★★☆ | ☆☆☆ |
| **Speed (H100)** | ~1.44 pp/s | Fast | Fast (SaaS) | Medium | Slow |
| **License** | OpenRAIL-M* | Paid SaaS | Paid SaaS | GPL-3.0 | MIT |
| **GPU required** | Yes (rec.) | No | No (SaaS) | Optional | Yes |
| **Local inference** | Yes | No | No | Yes | Yes |

*\*Free for research/personal/startups <$2M. Requires commercial license otherwise.*

---

## Performance & Throughput

**vLLM on NVIDIA H100 80GB:**

| Metric | Value |
|---|---|
| Pages/second | 1.44 |
| Average latency | 60s |
| P95 latency | 156s |
| Failure rate | 0% |
| Real-world estimate | ~2 pages/s |

---

## Usage

### Installation

```bash
pip install chandra-ocr         # base
pip install chandra-ocr[hf]     # with HuggingFace (requires torch)
pip install chandra-ocr[all]    # all extras
```

### CLI

```bash
# With vLLM server (start first with: chandra_vllm)
chandra input.pdf ./output

# With HuggingFace
chandra input.pdf ./output --method hf
```

### Python API — vLLM (recommended)

```python
from chandra.model import InferenceManager
from chandra.model.schema import BatchInputItem
from PIL import Image

manager = InferenceManager(method="vllm")
batch = [
    BatchInputItem(
        image=Image.open("document.png"),
        prompt_type="ocr_layout"
    )
]
result = manager.generate(batch)[0]
print(result.markdown)
```

### Python API — HuggingFace

```python
from transformers import AutoModelForImageTextToText, AutoProcessor
from chandra.model.hf import generate_hf
from chandra.model.schema import BatchInputItem
from chandra.output import parse_markdown
from PIL import Image
import torch

model = AutoModelForImageTextToText.from_pretrained(
    "datalab-to/chandra-ocr-2",
    dtype=torch.bfloat16,
    device_map="auto",
)
model.eval()
model.processor = AutoProcessor.from_pretrained("datalab-to/chandra-ocr-2")
model.processor.tokenizer.padding_side = "left"

batch = [
    BatchInputItem(
        image=Image.open("document.png"),
        prompt_type="ocr_layout"
    )
]
result = generate_hf(batch, model)[0]
markdown = parse_markdown(result.raw)
print(markdown)
```

---

## Datalab API: Structured Extraction with Confidence Scoring

Beyond OCR, Datalab offers a hosted API with **per-field confidence scoring** for structured data extraction.

### Confidence Scoring

Each extracted field gets a score from 1–5 with reasoning:

| Score | Meaning |
|---|---|
| 5 | High confidence — clear match with strong citation |
| 4 | Good confidence — match found with minor ambiguity |
| 3 | Moderate confidence — partial or uncertain evidence |
| 2 | Low confidence — inferred or weakly supported |
| 1 | Very low confidence — no clear evidence found |

### Two Scoring Modes

**Async (recommended):**
1. Extract with `save_checkpoint=true` → `POST /api/v1/extract`
2. Poll `request_check_url` until complete
3. Submit `checkpoint_id` to `POST /api/v1/extract/score`
4. Poll for scoring results

**Sync:**
- Pass `include_scores=true` to `POST /api/v1/extract` — returns extraction + scores in one call

### Response Fields

```json
{
  "field_name": "value",
  "field_name_citations": ["block_id"],
  "field_name_score": {
    "score": 4,
    "reasoning": "Clear match found in paragraph 2"
  },
  "extraction_score_average": 4.2
}
```

Use `extraction_score_average` for quick quality checks. Route fields scoring ≤2 to human review.

---

## Relevance to docfold

### Why Add Chandra

1. **Best-in-class OCR accuracy** — 85.9% on olmOCR, significantly beating Marker (76.5%) and Mistral OCR (72.0%)
2. **True local inference** — unlike Marker/LlamaParse/Mistral OCR which are SaaS-only, Chandra runs locally via vLLM or HuggingFace
3. **Strongest multilingual support** — 90+ languages at 77.8% average, filling a gap for non-English documents
4. **Handwriting + forms** — unique strength among local engines, none of the current 16 engines excel at handwriting
5. **Structured output** — native Markdown/HTML/JSON output aligns perfectly with docfold's `EngineResult` model
6. **Confidence scoring** — the Datalab API's per-field scoring maps well to docfold's quality assessment utilities

### Concerns

1. **GPU requirement** — the 5B VLM needs significant GPU memory (~16GB+ VRAM), limiting CPU-only environments
2. **License restrictions** — OpenRAIL-M is not fully permissive; commercial use above $2M threshold requires paid license
3. **Speed** — at ~1.44 pp/s on H100, significantly slower than PyMuPDF or text-based engines
4. **Dual mode complexity** — supporting both vLLM and HuggingFace backends adds adapter complexity
5. **Heavy dependencies** — `torch`, `transformers`, `vllm` are large packages

### Integration Approach

The engine should be implemented similarly to other VLM-based engines (like `zerox_engine.py` / `nougat_engine.py`):
- Lazy model loading on first `process()` call
- Support both vLLM (remote server) and HuggingFace (local) backends
- Map Chandra's markdown/HTML output to `EngineResult`
- Optional dependency via `pip install docfold[chandra]`

---

## References

- GitHub: https://github.com/datalab-to/chandra
- HuggingFace: https://huggingface.co/datalab-to/chandra-ocr-2
- Datalab API: https://www.datalab.to/
- Confidence Scoring Docs: https://documentation.datalab.to/docs/recipes/structured-extraction/confidence-scoring
- Playground: https://www.datalab.to/playground

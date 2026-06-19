---
purpose: "Evaluate spinning up a sibling project `ragfold` — a RAG aggregator + benchmark harness — and decide where PixelRAG-style visual RAG belongs"
status: "OPEN"
priority: "P2"
created: "2026-06-19"
---

# Feature: ragfold — RAG aggregator & benchmark harness

> This is a **strategy / scoping proposal**, not a docfold code change. It records
> the evaluation of [PixelRAG](https://github.com/StarTrail-org/PixelRAG) and the
> idea of a sibling project `ragfold`. Outcome wanted: a go / no-go decision and,
> if go, an MVP scope. No docfold source files change as a result of this doc.

## Problem

PixelRAG was raised as "isn't this useful to us?". It is **not** a fit for docfold:
docfold's entire contract is *document → structured text* (`EngineResult.content`
is a markdown/html/json/text string, see `src/docfold/engines/base.py:100`). Every
one of the 25 engines parses pixels/PDF **into text**. PixelRAG does the opposite —
it is OCR-free *visual retrieval*: it renders pages to image tiles, embeds them with
a VLM (`Qwen3-VL-Embedding`), and serves visual search. Its output is embeddings /
retrieved tiles, not a `content` string. It cannot satisfy `DocumentEngine`.

But the underlying question is real and recurring for every team building on top of
docfold:

> "Should I parse my documents to text (and with **which** docfold engine) and run
> text-RAG — or go visual/OCR-free (PixelRAG, ColPali)? Which wins **on my
> documents**, on both answer accuracy and token cost?"

Nobody owns this question well today. The generic RAG-framework layer (LangChain,
LlamaIndex, Haystack, RAGFlow) and the generic RAG-eval layer (RAGAS, TruLens,
DeepEval, Braintrust) are crowded and mature — we should **not** compete there.
The gap is the *bridge*: how the **ingestion/parsing choice** propagates into
retrieval and answer quality, with visual RAG treated as a first-class alternative.
We are uniquely positioned for it because we own the parsing layer (docfold).

### Why now
- Visual/OCR-free RAG crossed from research to production hype in 2025–2026
  (ColPali SOTA on ViDoRe; PixelRAG reports +18.1% accuracy and ~10× lower agent
  token cost vs. text parsers). Datasets exist (ViDoRe, UNIDOC-BENCH, REAL-MM-RAG)
  but there is no pluggable, parser-aware A/B harness on top of them.
- docfold already ships the reusable benchmark DNA we'd build on: pluggable
  engines, a metrics module, an evaluation runner, and a `compare` CLI.

## Proposed Solution

Create a **separate package `ragfold`** (own repo, depends on `docfold`), scoped
strictly as a **benchmark / comparison harness — NOT a RAG framework**. It mirrors
docfold's proven pattern one layer up.

Pipeline stages, each pluggable:

```
ingest  →  chunk / embed / index  →  retrieve  →  generate
  │                                      │
  └─ text path: docfold engine           └─ visual path: PixelRAG / ColPali
     (PyMuPDF, Docling, MinerU, …)          (image tiles, OCR-free)
```

The unit of pluggability is a `RagEngine` returning a `RetrievalResult` /
`RagAnswer`, by direct analogy to docfold's `DocumentEngine` → `EngineResult`.
A `text-rag` engine takes a `docfold` engine name as config, so the harness can
sweep *parser × retriever × generator* and report the trade-off matrix.

Benchmarks at two levels (reuse docfold metric conventions: predicted-first,
float score):
- **Retrieval:** recall@k, nDCG@k, MRR.
- **Answer:** accuracy/EM/F1 vs. gold, faithfulness (LLM-judge), + **token cost**
  and latency as first-class columns (PixelRAG's headline claim is cost).

Headline deliverable, mirroring `docfold compare`:
`ragfold compare my_docs/ --engines text-rag:pymupdf,text-rag:docling,visual:pixelrag`
→ one table: accuracy vs. cost vs. latency, per engine.

### Unique angle (what we sell / don't sell)
- ❌ Not an orchestrator (LangChain) and ❌ not another eval lib (RAGAS).
- ✅ "The only benchmark that tells you, on **your** documents, whether to
  parse-to-text (and with which parser) or go visual — by accuracy **and** cost."
  Defensible because it requires owning the parsing layer, which the eval
  incumbents do not.

## Affected Files

None in docfold (this is a scoping doc). If approved, work happens in a new repo.
Indicative `ragfold` skeleton (mirrors docfold layout):
- `ragfold/engines/base.py` — `RagEngine` ABC, `RetrievalResult`, `RagAnswer`
  (analogues of `docfold/engines/base.py`).
- `ragfold/engines/text_rag_engine.py` — wraps a `docfold` engine + embedder + store.
- `ragfold/engines/pixelrag_engine.py` — visual, OCR-free; first PixelRAG adapter.
- `ragfold/evaluation/metrics.py` — recall@k, nDCG, MRR, faithfulness, token cost.
- `ragfold/evaluation/runner.py` — sweep parser × retriever × generator.
- `ragfold/cli.py` — `ragfold compare`.

## Test Plan

### Unit / Functional Tests
- [ ] Retrieval metrics: recall@k / nDCG@k / MRR on hand-built fixtures with known
      gold ranks (perfect, reversed, partial).
- [ ] `RagEngine` contract: a stub engine satisfies the ABC and returns a
      well-formed `RetrievalResult` / `RagAnswer`.
- [ ] `text-rag` engine accepts a docfold engine name and threads it through ingest.
- [ ] Token-cost accounting is computed and surfaced per engine.

### Integration / E2E Tests
- [ ] Tiny fixture corpus (a few PDFs incl. a table-heavy page) end-to-end through
      one text-rag path and one visual path; `compare` emits a populated table.
- [ ] Same query across both paths produces comparable, schema-valid scores.

### Test Commands
```bash
# In the ragfold repo
pytest tests/
pytest tests/ -m "not slow"   # skip GPU/model-download tests
```

## Edge Cases
- GPU / large-model unavailable in CI → visual engines must degrade to skipped
  (mark `slow`), like docfold's optional-dependency `is_available()` pattern.
- Gold-label-free corpora → support reference-free (LLM-judge) metrics only.
- Embedding/index size blowup (PixelRAG's Wikipedia index is 217 GB+) → MVP runs
  only on small local corpora; no hosted-index requirement.
- Non-determinism of LLM judges → fix seeds/temperature, report variance.

## Out of Scope
- Becoming a RAG **framework** / orchestrator (LangChain/LlamaIndex territory).
- Production serving, agents, or a hosted index.
- Any change to docfold's public API or engine contract.
- Adding PixelRAG (or any retriever) **into** docfold as a `DocumentEngine` — it
  does not produce `EngineResult.content` and must not be forced to.

## Open Questions (for the go/no-go decision)
1. Separate repo `ragfold` (recommended) vs. a `docfold` subpackage? Separate keeps
   docfold's lean, parsing-only scope and heavy RAG deps out of it.
2. First visual engine: PixelRAG, ColPali, or both? (ColPali has the more
   established ViDoRe benchmark; PixelRAG has the cost story.)
3. Which starter dataset(s): UNIDOC-BENCH / ViDoRe / REAL-MM-RAG, or a small
   in-house finance/insurance set closer to Datatera's domain?

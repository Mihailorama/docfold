---
purpose: "Split one PDF holding several documents into page ranges, one per document"
status: "DONE"
priority: "P1"
created: "2026-11-10"
---

# Feature: document splitting (page classification)

Plane: DOCFOLD-9.

## Problem
People upload one PDF or scan that holds several documents: four acceptance acts, a
cost certificate and a specification, or an invoice, an act and a UPD. Extraction reads
a file as one document, so rows from different documents mix and long files time out.
Callers need each document's page range and type before extraction.

## Proposed Solution
`docfold.split`:

- `split_document(path, types, classifiers)` labels every page (title, printed page
  number, type, "starts a new document") and groups pages into documents. It returns
  `SplitResult(pages, documents=[SplitDocument(type, start, end)], method, error)`;
  `to_dict()` gives `{"pages", "documents": [{"type", "start", "end", "pages": "1-5"}],
  "method"}`.
- Page classifiers are tried in order; one may abstain (`Abstain`) and the next runs:
  - `TextPageClassifier` (`method="heuristic"`, no model): text-layer pages only; a
    page starts a document when its head names a type followed by a number sign
    ("Счет-фактура № 179", "Act No. 2") or carries an OKUD form code naming one of the
    types. Abstains on scans or when the first page has no title.
  - `LLMPageClassifier` (`method="llm"`): text pages go 30 per call, scanned pages one
    image per call. `models` is an ordered fallback chain of LiteLLM model names or
    kwargs dicts (`{"model": ..., "api_key": ..., "vision": False}`); a failing model
    hands the call to the next one. `acompletion` can be injected (a caller's own LLM
    gateway); by default it is `litellm.acompletion`.
- A failed classifier never fails the caller: the file comes back as one untyped
  document (`method="fallback"`, `error`). Single pages, non-PDFs, no types → `single`;
  more than `max_pages` → `too_long`; scans with no vision model → `no_vision`.
- `cut_pages(path, "5-7")` rewrites a PDF in place to a page range, deterministically
  (same input, same bytes), so an OCR cache keyed by file hash is reused.

## Affected Files
- `src/docfold/split.py` - new module
- `pyproject.toml` - `[split]` extra (PyMuPDF), `[split-llm]` (+ litellm); PyMuPDF in `[test]`
- `tests/test_split.py` - tests

## Test Plan
- [x] grouping: titles start documents, running headers and printed page > 1 do not
- [x] short type names match whole words only; a title naming two types keeps the model's type
- [x] LLM: text pages batched, scans one image per call; fallback chain moves to the next model
- [x] heuristic: text-layer PDF split without a model; abstains on scans; chain falls through to LLM
- [x] single page / no types / failures read the file whole
- [x] `cut_pages` keeps the range and is deterministic
- [x] E2E: 26-page scan of nine construction documents → nine exact ranges (Claude Haiku 5.5)

## Edge Cases
- Free vision models misread several page images in one call: scans go one per call.
- Reasoning models spend `max_tokens` on thinking: budget is 200 tokens per page + 2000.
- Rate limits (HTTP 429): the same model is retried 3 times with growing waits before the
  next model in the chain.

## Out of Scope
- OCR-based heuristics for scans (the LLM engine reads the page image instead).
- Files longer than `max_pages` (default 60) are returned whole.

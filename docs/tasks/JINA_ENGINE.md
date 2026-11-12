---
purpose: "Jina Reader as a PDF engine"
status: "DONE"
priority: "P3"
created: "2026-11-12"
---

# Feature: Jina Reader engine (DOCFOLD-19)

## Proposed Solution
`JinaEngine(api_key=None, base_url="https://r.jina.ai/", timeout=180)`, name
`jina`: POSTs `{"pdf": <base64>}` with `X-Return-Format` markdown / html /
text, returns `data.content`; JSON output `{"title", "content"}`;
`metadata`: `title`, `tokens`. Key from the argument, `JINA_API_KEY` or
`JINAAI_API_KEY`; unavailable without one (the file leaves the machine).
After `firecrawl` in the PDF priority list.

## Test Plan
- [x] request body, headers per format, result mapping (local HTTP server)
- [x] availability from env

```bash
pytest tests/engines/test_jina_engine.py -v
```

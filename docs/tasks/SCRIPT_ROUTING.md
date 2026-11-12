---
purpose: "Pick OCR fallback engines by the document's script"
status: "DONE"
priority: "P1"
created: "2026-11-12"
---

# Feature: Script-aware OCR routing (DOCFOLD-12)

## Problem
Some engines fail on some scripts: docling produces garbage on Arabic and
Hebrew, slow CPU backends cannot take long documents. The router has no script
signal, so callers detect the script themselves and build the retry chain.

## Proposed Solution
- `docfold.utils.script`:
  - `ScriptHint` (`arabic` = Arabic + Hebrew/RTL, `cjk`, `cyrillic`,
    `latin`, `unknown`).
  - `detect_script_hint(text)`: Unicode ranges. RTL or CJK at >= 5% of letters
    (and >= 3 chars) wins, because even a minority breaks some engines; else
    Cyrillic vs Latin majority; fewer than 20 letters = `unknown`.
  - `detect_script_from_image(path)`: Tesseract OSD (`pytesseract`), mapped
    to `ScriptHint`; `unknown` on any failure.
  - `detect_document_script(path, text="")`: text first, then OSD on page 1
    of a PDF (or the image itself).
  - `ScriptRouting(rules, default, max_pages)`: callable for the router that
    returns the retry chain for the detected script and drops engines whose
    page limit the document exceeds.
- `EngineRouter.process(fallback_engines=callable)`: the callable runs only
  when the primary attempt fails (gate or error) and gets
  `(primary_result_or_None, file_path)`. It returns the list of engines, or
  `(list, info)`; `info` is merged into the primary `fallback_chain` record
  (`ScriptRouting` adds `script_hint`).

Defaults: `rules={"arabic": ["marker"]}`,
`default=["docling", "docling_serve", "marker"]`, `max_pages={"docling_serve": 5}`.

## Affected Files
- `src/docfold/utils/script.py` (new), `src/docfold/engines/router.py`

## Test Plan
- [x] script detection: Latin, Cyrillic, Arabic minority in English text, Hebrew, CJK, short text
- [x] OSD parsing (pytesseract mocked), failure -> unknown
- [x] document detection: text first, OSD on a rendered PDF page when text is empty
- [x] ScriptRouting chains: RTL -> marker, page limit drops docling_serve
- [x] router: callable invoked only on primary failure; `script_hint` recorded

```bash
pytest tests/utils/test_script.py tests/engines/test_router_quality_gate.py -v
```

## Edge Cases
- No pytesseract / no tesseract binary: `unknown`, default chain.
- Primary raised: callable gets `None`; detection falls back to OSD.

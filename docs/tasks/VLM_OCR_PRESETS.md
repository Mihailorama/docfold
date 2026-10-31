---
purpose: "Integrate the 2026 open OCR-VLM wave through one OpenAI-compatible engine with per-model presets"
status: "DONE"
priority: "P1"
created: "2026-10-31"
---

# Feature: VLM OCR presets

## Problem
The MiniCPM-OCR 1.0 README's "Efficiency vs. Performance" chart lists the current
open OCR models: MiniCPM-OCR, Xiaomi-OCR-0, PaddleOCR-VL-1.6, Ovis-OCR2,
chandra-ocr-2, TeleOCR, MinerU2.5-Pro, Unlimited-OCR-2, HunyuanOCR-1.5, GLM-OCR,
Surya-OCR-2, dots.ocr, LightOnOCR-3-1B. docfold covers few of them, and the ones
it does (chandra, surya, unlimited_ocr) use one in-process adapter per model.
That approach costs one module plus one torch dependency set per model.

## Proposed Solution
Many of these models are served through vLLM / SGLang / Ollama / llama.cpp,
which expose the same OpenAI-compatible `/v1/chat/completions` endpoint. One
adapter, `VLMOCREngine`, sends each page image plus the model's documented prompt
there. A `PRESETS` table maps engine name → HF model id, prompt, optional
system message, request params and a reply post-processor.

Shipped presets (only the models whose card documents a whole-page,
single-call prompt): `xiaomi_ocr`, `hunyuan_ocr`, `lighton_ocr`, `ovis_ocr2`,
`dots_ocr`. chandra-ocr-2 is already served over vLLM by the `chandra` engine.
The rest need a layout pass or a patched server; see
[LAYOUT_PIPELINE_OCR_MODELS.md](LAYOUT_PIPELINE_OCR_MODELS.md).

- Each preset registers as its own engine (`--engine lighton_ocr`).
- A preset is available only when `DOCFOLD_<PRESET>_URL` is set; optional
  `DOCFOLD_<PRESET>_MODEL` and `DOCFOLD_<PRESET>_API_KEY` env vars.
- HTTP uses stdlib `urllib`, so no new dependency. PDFs are rendered with PyMuPDF.
- Native in-process engines (chandra, surya, mineru, paddleocr, unlimited_ocr)
  stay untouched; preset names never shadow them.

## Affected Files
- `src/docfold/engines/vlm_ocr_engine.py`: NEW adapter + presets
- `src/docfold/cli.py`: register every preset in `_build_router()`
- `tests/engines/test_vlm_ocr_engine.py`: NEW
- `README.md`, `CHANGELOG.md`: documentation

## Test Plan
- [x] Presets: every entry has an HF id and a prompt; no name collides with a native engine
- [x] Unknown preset raises `ValueError`
- [x] Availability follows `DOCFOLD_<PRESET>_URL`; trailing slash normalised
- [x] Request payload: image as base64 data URL, prompt, bearer key, `/chat/completions` URL
- [x] Multi-page PDF → one request per page, JSON output keeps page order
- [x] Markdown code fence around the reply is stripped

```bash
pytest tests/engines/test_vlm_ocr_engine.py -v
```

## Edge Cases
- A reply wrapped in a ```` ```markdown ```` fence is unwrapped.
- No URL configured → engine registered but unavailable, router skips it.

## Out of Scope
- Bounding boxes / layout JSON that some models (dots.ocr, PaddleOCR-VL) can emit.
- Concurrent page requests.
- Live GPU E2E in CI.

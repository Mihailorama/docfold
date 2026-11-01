---
purpose: "Integrate the open OCR models that need a layout pass or a patched server"
status: "DONE"
priority: "P2"
created: "2026-10-31"
---

# Feature: Layout-pipeline OCR models

Tracker: Plane project DOCFOLD — GPU check [DOCFOLD-1](https://tasks.aiagentlbs.com/sg/browse/DOCFOLD-1/),
MinerU 4 bug [DOCFOLD-2](https://tasks.aiagentlbs.com/sg/browse/DOCFOLD-2/), Surya 2 bug [DOCFOLD-3](https://tasks.aiagentlbs.com/sg/browse/DOCFOLD-3/),
TeleOCR [DOCFOLD-4](https://tasks.aiagentlbs.com/sg/browse/DOCFOLD-4/), extras [DOCFOLD-5](https://tasks.aiagentlbs.com/sg/browse/DOCFOLD-5/).

## Problem
Of the models on the MiniCPM-OCR 1.0 benchmark chart, these did not fit the
single-call `VLMOCREngine` presets ([VLM_OCR_PRESETS.md](VLM_OCR_PRESETS.md)):
their cards document region-level prompts only, a two-step client, or a
server that stock vLLM cannot run.

## Solution
| Model | Engine | How |
|-------|--------|-----|
| MiniCPM-OCR 1.0 | `minicpm_ocr` (new) | Runs the SDK's `minicpmvocr parse` CLI (PP-DocLayoutV3 + model server) |
| GLM-OCR | `glm_ocr` (new) | `glmocr.GlmOcr` in self-hosted mode |
| PaddleOCR-VL-1.6 | `paddleocr_vl` (new) | `paddleocr.PaddleOCRVL` with `vl_rec_backend="vllm-server"` |
| MinerU2.5-Pro | `mineru` | MinerU 4.x `mineru.parse` (its VLM is MinerU2.5-Pro); fixes the 4.x ImportError |
| Surya-OCR-2.5 | `surya` | Surya 2 `SuryaInferenceManager` path; fixes the `surya.foundation` ImportError |
| Unlimited-OCR-2 | `unlimited_ocr` | Default model is now v2: `infer` for one page, `infer_multi` for documents |
| TeleOCR | — | Not integrated: no OpenAI-compatible server ([DOCFOLD-4](https://tasks.aiagentlbs.com/sg/browse/DOCFOLD-4/)) |

New engines read the server from `DOCFOLD_<ENGINE>_URL` (".../v1") and stay
unavailable until it is set. Old MinerU (2.x/3.x) and Surya releases keep
their previous code paths.

## Verification
- Unit tests: `tests/engines/test_layout_pipeline_engines.py`, `test_mineru4.py`,
  `test_surya2.py`, `test_unlimited_ocr2.py`.
- Real packages: `minicpmvocr parse --help` flags; `glmocr.load_config` with
  the adapter's overrides; MinerU 4.1.3 end to end on CPU (`tier="flash"`);
  surya 0.23 end to end against an OpenAI-compatible stub; Unlimited-OCR-2
  remote-code `infer`/`infer_multi` signatures.
- Real models (2026-10-31, Apple M2 + llama-server GGUF Q8_0, layout on CPU),
  image-only scanned PDF: all of `lighton_ocr`, `hunyuan_ocr`, `xiaomi_ocr`
  (OTSL → HTML with `colspan`), `dots_ocr`, `ovis_ocr2`, `glm_ocr`,
  `minicpm_ocr` (llama.cpp ≥ b11901, `backend="llamacpp"`) and `paddleocr_vl`
  (`backend="llama-cpp-server"`) returned the correct text.
- Not run: Unlimited-OCR-2 (its remote code calls `.cuda()`), vLLM serving
  paths, large documents — [DOCFOLD-1](https://tasks.aiagentlbs.com/sg/browse/DOCFOLD-1/).

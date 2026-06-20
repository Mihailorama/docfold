# extractfold

**Turn any document into schema-conformant structured data.** A unified Python
interface over structured-data extraction engines — one contract, pluggable
engines, built-in evaluation.

> Sibling project to [**docfold**](https://github.com/mihailorama/docfold).
> Where docfold turns a document into a *representation* (Markdown / HTML / text /
> layout), extractfold turns a document **+ a JSON Schema** into a *filled,
> schema-conformant dict*. Use docfold when you want the document's content; use
> extractfold when you know exactly which fields you need.

## Why a separate project?

The two problems have genuinely different contracts:

| | docfold | extractfold |
|---|---|---|
| Input | document | document **+ JSON Schema** |
| Output | `content: str` (Markdown/HTML/text) | `data: dict` conforming to schema |
| Enrichments | bbox, reading order, table structure | per-field confidence, per-field provenance |
| Quality metric | WER/CER, reading order, table TEDS | field accuracy, schema compliance |
| Engine ecosystem | Docling, MinerU, Marker, OCR… | Lift, NuExtract, LLM structured outputs, LlamaExtract |

extractfold can also *use* docfold as a preprocessing step (get clean text first,
then extract), while VLM engines like Lift consume the document directly.

## Install

```bash
pip install extractfold[lift]          # Lift engine, vLLM backend (default)
pip install extractfold[lift-hf]       # Lift via local HuggingFace (needs a GPU)
pip install extractfold[evaluation]    # jsonschema-based compliance checks
pip install extractfold[all]
```

## Quick start

```python
import asyncio
from extractfold import ExtractionRouter, LiftEngine

router = ExtractionRouter([LiftEngine(method="vllm")])

schema = {
    "type": "object",
    "properties": {
        "invoice_number": {"type": "string"},
        "total": {"type": "number"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount": {"type": "number"},
                },
            },
        },
    },
}

async def main():
    result = await router.extract("invoice.pdf", schema)
    print(result.data)          # dict conforming to the schema
    print(result.metadata)      # model, token count, page count

asyncio.run(main())
```

Point at a remote vLLM server:

```bash
lift_vllm                                  # start a server (H100 defaults)
export VLLM_API_BASE=http://your-host:8000 # or pass vllm_api_base= to LiftEngine
```

## Engines

| Engine | extractfold | Type | License | Schema | Nested | Notes |
|--------|:-----------:|------|---------|:------:|:------:|-------|
| [**Lift**](https://github.com/datalab-to/lift) | ✅ | Local/VLM (9B) | Open | ✅ | ✅ | 90.2% on Datalab's benchmark |
| NuExtract | ⏳ | Local/VLM | Open | ✅ | ✅ | Planned |
| LLM structured outputs (Claude/GPT/Gemini) | ⏳ | API | Paid | ✅ | ✅ | Planned |
| LlamaExtract | ⏳ | SaaS | Paid | ✅ | ✅ | Planned |

## Evaluation

```python
from extractfold.evaluation import field_accuracy, schema_compliance

report = field_accuracy(result.data, gold_data)
print(report["accuracy"], report["mismatched"], report["missing"])

assert schema_compliance(result.data, schema)   # needs extractfold[evaluation]
```

## Status

Alpha. The core contract (`ExtractionEngine` / `ExtractionResult` /
`ExtractionRouter`) and the Lift engine are in place; more engines and a CLI are
on the roadmap.

## License

MIT

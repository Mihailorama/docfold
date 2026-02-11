# Evaluation Framework

Docfold includes a built-in evaluation framework for objectively comparing document structuring engines against ground truth annotations.

## Quick Start

```bash
pip install docfold[evaluation]
docfold evaluate path/to/dataset/ --engines docling,pymupdf --output report.json
```

## Dataset Structure

Organize your evaluation dataset by document category:

```
dataset/
  invoices/
    inv_001.pdf
    inv_001.ground_truth.json
    inv_002.pdf
    inv_002.ground_truth.json
  academic_papers/
    paper_001.pdf
    paper_001.ground_truth.json
  contracts/
    contract_001.docx
    contract_001.ground_truth.json
```

Each document must have a matching `.ground_truth.json` file with the same stem.

## Ground Truth JSON Schema

```json
{
  "document_id": "inv_001",
  "category": "invoice",
  "source": "manually annotated",
  "ground_truth": {
    "full_text": "The complete text content of the document as it should be extracted...",
    "headings": [
      "Invoice #12345",
      "Bill To",
      "Items",
      "Total"
    ],
    "tables": [
      [
        ["Item", "Qty", "Price"],
        ["Widget A", "10", "$5.00"],
        ["Widget B", "5", "$12.00"]
      ]
    ],
    "reading_order": [
      "Invoice #12345",
      "Date: 2026-01-15",
      "Bill To",
      "Acme Corp",
      "Items",
      "Total"
    ]
  }
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_id` | string | Yes | Unique identifier for the document |
| `category` | string | Yes | Category for filtering (e.g., "invoice", "academic", "contract") |
| `source` | string | No | How the ground truth was created |
| `ground_truth.full_text` | string | Yes | Complete reference text |
| `ground_truth.headings` | string[] | No | Expected headings in order |
| `ground_truth.tables` | string[][][] | No | Tables as list of rows of cells |
| `ground_truth.reading_order` | string[] | No | Expected reading order of text blocks |

## Metrics

### Character Error Rate (CER)

Levenshtein edit distance at the character level, normalized by reference length. Lower is better.

- **Perfect match**: 0.0
- **Typical good extraction**: < 0.05

### Word Error Rate (WER)

Edit distance at the word level, normalized by reference word count. Lower is better.

- **Perfect match**: 0.0
- **Typical good extraction**: < 0.10

### Table F1

Precision/recall at the cell level across all tables. Higher is better.

- **Perfect match**: 1.0
- **No tables detected**: 0.0

### Heading F1

Precision/recall on detected headings (case-insensitive). Higher is better.

### Reading Order Score

Kendall's tau rank correlation between predicted and reference reading order. Higher is better.

- **Perfect order**: 1.0
- **Completely reversed**: -1.0

## Programmatic Usage

```python
from docfold.engines.router import EngineRouter
from docfold.engines.docling_engine import DoclingEngine
from docfold.engines.pymupdf_engine import PyMuPDFEngine
from docfold.evaluation.runner import EvaluationRunner

router = EngineRouter([DoclingEngine(), PyMuPDFEngine()])
runner = EvaluationRunner(router, dataset_path="tests/evaluation/dataset")

report = await runner.run(
    engines=["docling", "pymupdf"],
    categories=["invoice"],
)

# Per-document scores
for score in report.scores:
    print(f"{score.document_id} ({score.engine_name}): CER={score.cer:.4f}")

# Aggregated summaries
for engine, summary in report.engine_summaries.items():
    print(f"{engine}: avg_cer={summary['avg_cer']:.4f}, avg_wer={summary['avg_wer']:.4f}")

# Export
report_json = report.to_json()
```

## Creating Ground Truth

Recommended workflow:

1. **LLM-assisted**: Use an LLM to generate initial annotations from the source document
2. **Human review**: Have a domain expert review and correct the annotations
3. **Version control**: Keep ground truth files in git alongside the source documents
4. **Small corpus**: Start with 5-10 documents per category, expand as needed

## Tips

- Keep source documents small (< 5 pages) for faster iteration
- Use diverse documents within each category
- Include edge cases: rotated pages, multi-column layouts, handwritten notes
- Run evaluation after each engine update to track quality regressions

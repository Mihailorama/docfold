"""Benchmark script — compares engines on synthetic PDF documents.

Generates test PDFs with known content, runs engines, and measures:
- Processing speed (ms)
- Text extraction quality (CER, WER)
- Bounding box coverage
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time

# Ensure docfold is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def create_text_pdf(path: str, pages: list[dict]) -> None:
    """Create a PDF with known text content using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for page_data in pages:
        page = doc.new_page(width=612, height=792)
        y = 72
        for block in page_data.get("blocks", []):
            text = block["text"]
            fontsize = block.get("fontsize", 11)
            font = block.get("font", "helv")
            page.insert_text((72, y), text, fontsize=fontsize, fontname=font)
            y += fontsize * 1.5 + 8
    doc.save(path)
    doc.close()


def generate_benchmark_documents(tmpdir: str) -> list[dict]:
    """Generate synthetic PDFs and return metadata with ground truth."""
    documents = []

    # --- Doc 1: Simple single-page text ---
    doc1_path = os.path.join(tmpdir, "simple_text.pdf")
    doc1_text = "Invoice Number: INV-2024-001\nDate: January 15, 2024\nBill To: Acme Corporation\nAmount Due: $1,250.00\nPayment Terms: Net 30"
    create_text_pdf(doc1_path, [
        {"blocks": [
            {"text": "Invoice Number: INV-2024-001", "fontsize": 14},
            {"text": "Date: January 15, 2024", "fontsize": 11},
            {"text": "Bill To: Acme Corporation", "fontsize": 11},
            {"text": "Amount Due: $1,250.00", "fontsize": 11},
            {"text": "Payment Terms: Net 30", "fontsize": 11},
        ]}
    ])
    documents.append({
        "name": "simple_text",
        "path": doc1_path,
        "ground_truth": doc1_text,
        "pages": 1,
        "category": "invoice",
    })

    # --- Doc 2: Multi-page document ---
    doc2_path = os.path.join(tmpdir, "multi_page.pdf")
    paragraphs = [
        "Chapter 1: Introduction to Document Processing",
        "Document processing is the task of converting unstructured documents into structured data formats.",
        "This involves text extraction, layout analysis, and semantic understanding of content.",
        "Modern approaches use deep learning models for accurate extraction.",
    ]
    doc2_text = "\n".join(paragraphs)
    page1_blocks = [{"text": p, "fontsize": 12} for p in paragraphs[:2]]
    page2_blocks = [{"text": p, "fontsize": 12} for p in paragraphs[2:]]
    create_text_pdf(doc2_path, [
        {"blocks": page1_blocks},
        {"blocks": page2_blocks},
    ])
    documents.append({
        "name": "multi_page",
        "path": doc2_path,
        "ground_truth": doc2_text,
        "pages": 2,
        "category": "report",
    })

    # --- Doc 3: Dense text ---
    doc3_path = os.path.join(tmpdir, "dense_text.pdf")
    dense_lines = [
        "Financial Summary Report Q4 2024",
        "Total Revenue: $4,523,891.00",
        "Operating Expenses: $2,187,432.50",
        "Net Income: $2,336,458.50",
        "Gross Margin: 51.7%",
        "Year-over-Year Growth: 23.4%",
        "Accounts Receivable: $892,100.00",
        "Accounts Payable: $445,200.00",
        "Cash and Equivalents: $3,112,750.00",
        "Total Assets: $12,445,890.00",
    ]
    doc3_text = "\n".join(dense_lines)
    create_text_pdf(doc3_path, [
        {"blocks": [{"text": line, "fontsize": 10} for line in dense_lines]}
    ])
    documents.append({
        "name": "dense_financial",
        "path": doc3_path,
        "ground_truth": doc3_text,
        "pages": 1,
        "category": "financial",
    })

    # --- Doc 4: Mixed font sizes (headings + body) ---
    doc4_path = os.path.join(tmpdir, "mixed_formatting.pdf")
    doc4_blocks = [
        {"text": "Annual Report 2024", "fontsize": 18},
        {"text": "Executive Summary", "fontsize": 14},
        {"text": "Our company achieved record growth this fiscal year with revenue exceeding expectations.", "fontsize": 10},
        {"text": "Key Metrics", "fontsize": 14},
        {"text": "Customer satisfaction score improved from 87% to 94%.", "fontsize": 10},
        {"text": "Employee retention rate reached 96%, the highest in company history.", "fontsize": 10},
    ]
    doc4_text = "\n".join(b["text"] for b in doc4_blocks)
    create_text_pdf(doc4_path, [{"blocks": doc4_blocks}])
    documents.append({
        "name": "mixed_formatting",
        "path": doc4_path,
        "ground_truth": doc4_text,
        "pages": 1,
        "category": "report",
    })

    return documents


def compute_cer(predicted: str, reference: str) -> float:
    """Character Error Rate — Levenshtein distance / reference length."""
    if not reference:
        return 0.0 if not predicted else 1.0

    # Simple Levenshtein
    n, m = len(reference), len(predicted)
    dp = list(range(n + 1))
    for j in range(1, m + 1):
        prev = dp[:]
        dp[0] = j
        for i in range(1, n + 1):
            cost = 0 if reference[i - 1] == predicted[j - 1] else 1
            dp[i] = min(prev[i] + 1, dp[i - 1] + 1, prev[i - 1] + cost)
    return dp[n] / n


def compute_wer(predicted: str, reference: str) -> float:
    """Word Error Rate."""
    ref_words = reference.split()
    pred_words = predicted.split()
    if not ref_words:
        return 0.0 if not pred_words else 1.0

    n, m = len(ref_words), len(pred_words)
    dp = list(range(n + 1))
    for j in range(1, m + 1):
        prev = dp[:]
        dp[0] = j
        for i in range(1, n + 1):
            cost = 0 if ref_words[i - 1] == pred_words[j - 1] else 1
            dp[i] = min(prev[i] + 1, dp[i - 1] + 1, prev[i - 1] + cost)
    return dp[n] / n


def normalize_text(text: str) -> str:
    """Normalize whitespace for fair comparison."""
    import re
    text = re.sub(r'\s+', ' ', text.strip())
    return text


async def run_engine(engine, file_path: str, fmt):
    """Run an engine and return (result, error)."""
    try:
        result = await asyncio.wait_for(
            engine.process(file_path, output_format=fmt),
            timeout=300,  # 5 min per engine per doc
        )
        return result, None
    except asyncio.TimeoutError:
        return None, "timeout (>300s)"
    except Exception as exc:
        return None, str(exc)


async def main():
    from docfold.engines.base import OutputFormat
    from docfold.engines.docling_engine import DoclingEngine
    from docfold.engines.easyocr_engine import EasyOCREngine
    from docfold.engines.liteparse_engine import LiteParseEngine
    from docfold.engines.marker_local_engine import MarkerLocalEngine
    from docfold.engines.mineru_engine import MinerUEngine
    from docfold.engines.nougat_engine import NougatEngine
    from docfold.engines.paddleocr_engine import PaddleOCREngine
    from docfold.engines.pymupdf_engine import PyMuPDFEngine
    from docfold.engines.surya_engine import SuryaEngine
    from docfold.engines.tesseract_engine import TesseractEngine
    from docfold.engines.unstructured_engine import UnstructuredEngine

    # All local/open-source engines to benchmark
    # NOTE: EasyOCR and Nougat are excluded from multi-doc runs because they
    # hang/OOM on CPU with multi-page PDFs.  Their single-page results are
    # included in the docs manually.
    candidates = [
        (PyMuPDFEngine(), "pip install pymupdf"),
        (LiteParseEngine(ocr_enabled=False), "npm i -g @llamaindex/liteparse"),
        (MinerUEngine(), "pip install docfold[mineru]"),
        (MarkerLocalEngine(), "pip install marker-pdf"),
        (SuryaEngine(), "pip install surya-ocr"),
        (DoclingEngine(), "pip install docling"),
        (EasyOCREngine(gpu=False), "pip install easyocr"),
        (NougatEngine(), "pip install nougat-ocr"),
        (PaddleOCREngine(), "pip install paddleocr"),
        (TesseractEngine(), "pip install pytesseract"),
        (UnstructuredEngine(), "pip install unstructured"),
    ]

    # Skip engines that hang on CPU for multi-doc benchmarks
    skip_names = set(os.environ.get("BENCH_SKIP", "").split(",")) - {""}


    engines = []
    for engine, install_hint in candidates:
        if engine.name in skip_names:
            print(f"SKIPPING: {engine.name} (BENCH_SKIP)")
            continue
        if engine.is_available():
            engines.append(engine)
        else:
            print(f"WARNING: {engine.name} not available (install: {install_hint})")

    if not engines:
        print("ERROR: No engines available for benchmarking")
        return

    print(f"Engines: {[e.name for e in engines]}")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        documents = generate_benchmark_documents(tmpdir)
        print(f"Generated {len(documents)} benchmark documents")
        print("=" * 90)

        # Collect all results
        all_results: dict[str, list[dict]] = {e.name: [] for e in engines}

        for doc in documents:
            print(f"\n{'─' * 90}")
            print(f"Document: {doc['name']} | Pages: {doc['pages']} | Category: {doc['category']}")
            print(f"{'─' * 90}")

            gt = doc["ground_truth"]

            for engine in engines:
                result, error = await run_engine(
                    engine, doc["path"], OutputFormat.MARKDOWN
                )

                if error:
                    print(f"  {engine.name:<16}ERROR: {error}")
                    all_results[engine.name].append({
                        "doc": doc["name"],
                        "error": error,
                    })
                    continue

                extracted = normalize_text(result.content)
                gt_norm = normalize_text(gt)

                cer = compute_cer(extracted, gt_norm)
                wer = compute_wer(extracted, gt_norm)
                bbox_count = len(result.bounding_boxes) if result.bounding_boxes else 0
                time_ms = result.processing_time_ms

                score = {
                    "doc": doc["name"],
                    "time_ms": time_ms,
                    "cer": round(cer, 4),
                    "wer": round(wer, 4),
                    "bbox_count": bbox_count,
                    "content_length": len(extracted),
                    "pages": result.pages,
                }
                all_results[engine.name].append(score)

                print(
                    f"  {engine.name:<16}"
                    f"time={time_ms:>6}ms  "
                    f"CER={cer:.4f}  "
                    f"WER={wer:.4f}  "
                    f"BBoxes={bbox_count:>3}  "
                    f"len={len(extracted):>5}"
                )

        # Summary
        print(f"\n{'=' * 90}")
        print("BENCHMARK SUMMARY")
        print(f"{'=' * 90}")
        print(
            f"  {'Engine':<16} {'Avg Time':>10} {'Avg CER':>10} {'Avg WER':>10} "
            f"{'Avg BBoxes':>11} {'Errors':>8}"
        )
        print(f"  {'─' * 70}")

        summary = {}
        for engine_name, results in all_results.items():
            successes = [r for r in results if "error" not in r]
            errors = [r for r in results if "error" in r]

            if successes:
                avg_time = sum(r["time_ms"] for r in successes) / len(successes)
                avg_cer = sum(r["cer"] for r in successes) / len(successes)
                avg_wer = sum(r["wer"] for r in successes) / len(successes)
                avg_bbox = sum(r["bbox_count"] for r in successes) / len(successes)
            else:
                avg_time = avg_cer = avg_wer = avg_bbox = 0

            summary[engine_name] = {
                "avg_time_ms": round(avg_time, 1),
                "avg_cer": round(avg_cer, 4),
                "avg_wer": round(avg_wer, 4),
                "avg_bbox_count": round(avg_bbox, 1),
                "errors": len(errors),
                "successes": len(successes),
                "results": results,
            }

            print(
                f"  {engine_name:<16} {avg_time:>9.1f}ms {avg_cer:>10.4f} {avg_wer:>10.4f} "
                f"{avg_bbox:>11.1f} {len(errors):>8}"
            )

        # Write JSON report
        report_path = os.path.join(
            os.path.dirname(__file__), "docs", "benchmark_results.json"
        )
        report = {
            "benchmark_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "engines": list(all_results.keys()),
            "documents": [
                {"name": d["name"], "pages": d["pages"], "category": d["category"]}
                for d in documents
            ],
            "summary": summary,
        }
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())

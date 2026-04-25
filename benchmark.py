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


_FIXTURE_FONT_DIR = os.path.join(
    os.path.dirname(__file__), "tests", "fixtures", "fonts"
)


def _find_bundled_font(preferred: str, fallbacks: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Return ``(font_dir, ttf_name)`` for a font that exists on disk.

    Prefers the bundled fixture under ``tests/fixtures/fonts/`` (shipped under
    OFL-1.1) so the benchmark is reproducible on any host; falls back to
    system paths only as a safety net.
    """
    if os.path.exists(os.path.join(_FIXTURE_FONT_DIR, preferred)):
        return _FIXTURE_FONT_DIR, preferred
    for d, fname in fallbacks:
        if os.path.exists(os.path.join(d, fname)):
            return d, fname
    return None


def _find_arabic_font() -> tuple[str, str] | None:
    return _find_bundled_font(
        "NotoNaskhArabic-Regular.ttf",
        [
            ("/usr/share/fonts/truetype/noto", "NotoNaskhArabic-Regular.ttf"),
            ("/usr/share/fonts/noto", "NotoNaskhArabic-Regular.ttf"),
            ("/usr/share/fonts/truetype/noto", "NotoSansArabic-Regular.ttf"),
        ],
    )


def _find_script_font(preferred: str) -> tuple[str, str] | None:
    """Bundled fonts for non-Arabic scripts — no system fallback because the
    subsetted TTF is what we tested against."""
    return _find_bundled_font(preferred, [])


def _render_html_pdf(path: str, html_body: str, font_info: tuple[str, str]) -> None:
    """Generic HTML → PDF renderer using PyMuPDF's ``insert_htmlbox`` with
    a bundled font archive. Handles shaping / bidi via HarfBuzz under the hood.
    """
    import fitz

    font_dir, ttf = font_info
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    archive = fitz.Archive(font_dir)
    css = f"@font-face {{ font-family: 'BenchFont'; src: url({ttf}); }}"
    page.insert_htmlbox(fitz.Rect(36, 36, 576, 756), html_body, css=css, archive=archive)
    doc.save(path)
    doc.close()


def create_arabic_pdf(path: str, html_body: str) -> None:
    """Render an Arabic HTML snippet to PDF using Noto Naskh Arabic."""
    font_info = _find_arabic_font()
    if font_info is None:
        raise RuntimeError(
            "Arabic font fixture missing: "
            "tests/fixtures/fonts/NotoNaskhArabic-Regular.ttf"
        )
    _render_html_pdf(path, html_body, font_info)


def create_script_pdf(path: str, html_body: str, font_ttf: str) -> None:
    """Render an HTML snippet to PDF using a bundled script-specific font."""
    font_info = _find_script_font(font_ttf)
    if font_info is None:
        raise RuntimeError(f"Font fixture missing: tests/fixtures/fonts/{font_ttf}")
    _render_html_pdf(path, html_body, font_info)


def _extract_ground_truth(pdf_path: str) -> str:
    """Return PyMuPDF's extracted text — used as ground truth for docs whose
    authoritative form depends on font shaping (e.g. Arabic).
    """
    import fitz

    doc = fitz.open(pdf_path)
    text = "\n".join(p.get_text() for p in doc)
    doc.close()
    return text


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

    # --- Doc 5: Arabic (RTL + shaping) ---
    # PDFs store Arabic in shaped presentation forms and reverse visual order.
    # We use PyMuPDF's extraction of the generated PDF as ground truth — this
    # measures whether *other* engines agree on the same text, not whether
    # they normalize to logical Unicode (a harder task).
    doc5_path = os.path.join(tmpdir, "arabic_report.pdf")
    arabic_html = (
        '<div lang="ar" dir="rtl" '
        "style=\"font-family:'BenchFont';font-size:14pt;line-height:1.8;\">"
        "<h1>تقرير سنوي 2024</h1>"
        "<p>حققت الشركة نموا قياسيا هذا العام بإيرادات تجاوزت التوقعات.</p>"
        "<p>بلغت نسبة رضا العملاء 94 بالمئة.</p>"
        "<p>وصل معدل الاحتفاظ بالموظفين إلى 96 بالمئة.</p>"
        "</div>"
    )
    create_arabic_pdf(doc5_path, arabic_html)
    documents.append({
        "name": "arabic_report",
        "path": doc5_path,
        "ground_truth": _extract_ground_truth(doc5_path),
        "pages": 1,
        "category": "rtl",
    })

    # --- Doc 6: Simplified Chinese (CJK) ---
    # CJK has no shaping and LTR, but tests that engines don't mangle
    # multi-byte Unicode. Font is subsetted (60 KB) from Noto Sans CJK SC.
    doc6_path = os.path.join(tmpdir, "chinese_report.pdf")
    chinese_html = (
        '<div lang="zh" dir="ltr" '
        "style=\"font-family:'BenchFont';font-size:14pt;line-height:1.8;\">"
        "<h1>2024年度报告</h1>"
        "<p>公司今年实现了创纪录的增长，收入超出预期。</p>"
        "<p>客户满意度达到了94%。</p>"
        "<p>员工保留率达到96%，创公司历史新高。</p>"
        "</div>"
    )
    create_script_pdf(doc6_path, chinese_html, "NotoSansCJKsc-Regular-subset.ttf")
    documents.append({
        "name": "chinese_report",
        "path": doc6_path,
        "ground_truth": _extract_ground_truth(doc6_path),
        "pages": 1,
        "category": "cjk",
    })

    # --- Doc 7: Hebrew (RTL, no shaping) ---
    # Good contrast to Arabic: same RTL bidi, but no contextual shaping.
    doc7_path = os.path.join(tmpdir, "hebrew_report.pdf")
    hebrew_html = (
        '<div lang="he" dir="rtl" '
        "style=\"font-family:'BenchFont';font-size:14pt;line-height:1.8;\">"
        "<h1>דוח שנתי 2024</h1>"
        "<p>החברה השיגה צמיחה שיא השנה, עם הכנסות שעלו על הציפיות.</p>"
        "<p>שביעות רצון הלקוחות הגיעה ל-94 אחוז.</p>"
        "<p>שיעור שימור העובדים הגיע ל-96 אחוז.</p>"
        "</div>"
    )
    create_script_pdf(doc7_path, hebrew_html, "NotoSansHebrew-Regular-subset.ttf")
    documents.append({
        "name": "hebrew_report",
        "path": doc7_path,
        "ground_truth": _extract_ground_truth(doc7_path),
        "pages": 1,
        "category": "rtl",
    })

    # NOTE: Devanagari and Thai are intentionally omitted. PyMuPDF's
    # ``insert_htmlbox`` produces PDFs whose ToUnicode maps don't survive
    # round-trip extraction for those scripts (null bytes, dropped matras).
    # They need real-world fixture PDFs — see docs/tasks/ for a follow-up.

    # --- Doc 8: DOCX (Office) ---
    # Minimal valid Office Open XML built with stdlib only — no python-docx
    # dependency. Exercises engines that handle Office formats (markitdown,
    # docling, unstructured, liteparse, ...).
    doc8_path = os.path.join(tmpdir, "office_memo.docx")
    doc8_paragraphs = [
        "Internal Memo",
        "To: All Staff",
        "Date: April 25, 2026",
        "Subject: Q1 2026 Results",
        "Revenue grew 18 percent year-over-year, exceeding the plan.",
        "Operating margin improved to 24.1 percent.",
    ]
    create_docx(doc8_path, doc8_paragraphs)
    documents.append({
        "name": "office_memo",
        "path": doc8_path,
        "ground_truth": "\n".join(doc8_paragraphs),
        "pages": 1,
        "category": "office",
    })

    # --- Doc 9: HTML page ---
    doc9_path = os.path.join(tmpdir, "blog_post.html")
    doc9_paragraphs = [
        "How Document Processing Works",
        "Document processing converts unstructured files into structured data.",
        "Modern pipelines combine layout analysis, OCR, and language models.",
        "Open-source toolkits make these capabilities widely accessible.",
    ]
    doc9_html = (
        "<!DOCTYPE html><html><head><title>Doc Processing</title></head><body>"
        f"<h1>{doc9_paragraphs[0]}</h1>"
        + "".join(f"<p>{p}</p>" for p in doc9_paragraphs[1:])
        + "</body></html>"
    )
    with open(doc9_path, "w", encoding="utf-8") as f:
        f.write(doc9_html)
    documents.append({
        "name": "blog_post",
        "path": doc9_path,
        "ground_truth": "\n".join(doc9_paragraphs),
        "pages": 1,
        "category": "web",
    })

    # --- Doc 10: CSV (tabular) ---
    # Engines that target Markdown output (markitdown, docling, ...) render
    # CSV as a Markdown table.  The ground truth is the canonical Markdown
    # table so CER/WER measure formatting fidelity, not how cells are joined.
    doc10_path = os.path.join(tmpdir, "sales.csv")
    doc10_rows = [
        ["Region", "Q1", "Q2", "Q3", "Q4"],
        ["North", "120", "135", "150", "180"],
        ["South", "98", "110", "125", "140"],
        ["East", "85", "92", "100", "118"],
        ["West", "140", "155", "170", "200"],
    ]
    with open(doc10_path, "w", encoding="utf-8") as f:
        for row in doc10_rows:
            f.write(",".join(row) + "\n")
    header = doc10_rows[0]
    sep = ["---"] * len(header)
    md_lines = (
        ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
        + ["| " + " | ".join(row) + " |" for row in doc10_rows[1:]]
    )
    documents.append({
        "name": "sales_csv",
        "path": doc10_path,
        "ground_truth": "\n".join(md_lines),
        "pages": 1,
        "category": "tabular",
    })

    return documents


def create_docx(path: str, paragraphs: list[str]) -> None:
    """Build a minimal but valid .docx (Office Open XML) with no dependencies.

    Only enough structure to round-trip plain paragraphs through engines like
    python-docx, docling, markitdown, unstructured, liteparse, ...
    """
    import zipfile

    def _xml_escape(s: str) -> str:
        return (
            s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
        )

    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{_xml_escape(p)}</w:t></w:r></w:p>'
        for p in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}</w:body>'
        '</w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '</Relationships>'
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)


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
    from docfold.engines.markitdown_engine import MarkItDownEngine
    from docfold.engines.mineru_engine import MinerUEngine
    from docfold.engines.nougat_engine import NougatEngine
    from docfold.engines.opendataloader_engine import OpenDataLoaderEngine
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
        (OpenDataLoaderEngine(), "pip install docfold[opendataloader] (needs Java 11+)"),
        (MinerUEngine(), "pip install docfold[mineru]"),
        (MarkerLocalEngine(), "pip install marker-pdf"),
        (SuryaEngine(), "pip install surya-ocr"),
        (DoclingEngine(), "pip install docling"),
        (EasyOCREngine(gpu=False), "pip install easyocr"),
        (NougatEngine(), "pip install nougat-ocr"),
        (PaddleOCREngine(), "pip install paddleocr"),
        (TesseractEngine(), "pip install pytesseract"),
        (UnstructuredEngine(), "pip install unstructured"),
        (MarkItDownEngine(), "pip install docfold[markitdown]"),
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
            doc_ext = os.path.splitext(doc["path"])[1].lstrip(".").lower()

            for engine in engines:
                # Skip engines whose declared supported_extensions don't include
                # this doc's format — keeps the report free of noise like
                # "PyMuPDF can't open .docx".
                if doc_ext and doc_ext not in engine.supported_extensions:
                    continue

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

"""docfold CLI entry-point."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="docfold",
        description="Turn any document into structured data.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- convert ---
    convert_p = sub.add_parser("convert", help="Convert a document to structured text")
    convert_p.add_argument("file", help="Path to the input document")
    convert_p.add_argument(
        "-e", "--engine",
        help="Engine to use. Default: auto-select.",
    )
    convert_p.add_argument(
        "-f", "--format",
        choices=["markdown", "html", "json", "text"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    convert_p.add_argument(
        "-o", "--output",
        help="Output file path. If omitted, prints to stdout.",
    )
    convert_p.add_argument(
        "--engines",
        help="Comma-separated list of allowed engines (restricts selection).",
    )

    # --- engines ---
    sub.add_parser("engines", help="List available engines and their status")

    # --- compare ---
    compare_p = sub.add_parser("compare", help="Compare engines on a document")
    compare_p.add_argument("file", help="Path to the input document")
    compare_p.add_argument(
        "-e", "--engines",
        help="Comma-separated engine names. Default: all available.",
    )

    # --- evaluate ---
    eval_p = sub.add_parser("evaluate", help="Run evaluation benchmark")
    eval_p.add_argument("dataset", help="Path to evaluation dataset directory")
    eval_p.add_argument(
        "-e", "--engines",
        help="Comma-separated engine names. Default: all available.",
    )
    eval_p.add_argument(
        "-o", "--output",
        help="Output file for evaluation report (JSON).",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "convert":
        asyncio.run(_cmd_convert(args))
    elif args.command == "engines":
        _cmd_engines()
    elif args.command == "compare":
        asyncio.run(_cmd_compare(args))
    elif args.command == "evaluate":
        asyncio.run(_cmd_evaluate(args))


def _build_router():
    """Build a router with all discoverable engines."""
    from docfold.engines.router import EngineRouter

    router = EngineRouter()

    # Try importing each engine adapter; register if available
    try:
        from docfold.engines.docling_engine import DoclingEngine
        router.register(DoclingEngine())
    except Exception:
        pass

    try:
        from docfold.engines.mineru_engine import MinerUEngine
        router.register(MinerUEngine())
    except Exception:
        pass

    try:
        from docfold.engines.marker_engine import MarkerEngine
        router.register(MarkerEngine())
    except Exception:
        pass

    try:
        from docfold.engines.pymupdf_engine import PyMuPDFEngine
        router.register(PyMuPDFEngine())
    except Exception:
        pass

    try:
        from docfold.engines.paddleocr_engine import PaddleOCREngine
        router.register(PaddleOCREngine())
    except Exception:
        pass

    try:
        from docfold.engines.tesseract_engine import TesseractEngine
        router.register(TesseractEngine())
    except Exception:
        pass

    try:
        from docfold.engines.unstructured_engine import UnstructuredEngine
        router.register(UnstructuredEngine())
    except Exception:
        pass

    try:
        from docfold.engines.llamaparse_engine import LlamaParseEngine
        router.register(LlamaParseEngine())
    except Exception:
        pass

    try:
        from docfold.engines.mistral_ocr_engine import MistralOCREngine
        router.register(MistralOCREngine())
    except Exception:
        pass

    try:
        from docfold.engines.zerox_engine import ZeroxEngine
        router.register(ZeroxEngine())
    except Exception:
        pass

    try:
        from docfold.engines.textract_engine import TextractEngine
        router.register(TextractEngine())
    except Exception:
        pass

    try:
        from docfold.engines.google_docai_engine import GoogleDocAIEngine
        router.register(GoogleDocAIEngine())
    except Exception:
        pass

    try:
        from docfold.engines.azure_docint_engine import AzureDocIntEngine
        router.register(AzureDocIntEngine())
    except Exception:
        pass

    return router


async def _cmd_convert(args) -> None:
    from docfold.engines.base import OutputFormat

    allowed = set(args.engines.split(",")) if args.engines else None
    router = _build_router()
    if allowed:
        router._allowed_engines = allowed
    fmt = OutputFormat(args.format)

    result = await router.process(args.file, output_format=fmt, engine_hint=args.engine)

    output = result.content
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        eng = result.engine_name
        ms = result.processing_time_ms
        print(f"Written to {args.output} (engine={eng}, {ms}ms)")
    else:
        print(output)


def _cmd_engines() -> None:
    router = _build_router()
    engines = router.list_engines()

    if not engines:
        print("No engines registered. Install extras: pip install docfold[all]")
        return

    print(f"{'Engine':<14} {'Status':<9} {'BBox':>4} {'Conf':>4} {'Tbl':>4} {'Img':>4}  Formats")
    print("-" * 78)
    for e in engines:
        status = "YES" if e["available"] else "no"
        caps = e.get("capabilities", {})
        bbox = "+" if caps.get("bounding_boxes") else "-"
        conf = "+" if caps.get("confidence") else "-"
        tbl = "+" if caps.get("table_structure") else "-"
        img = "+" if caps.get("images") else "-"
        exts = ", ".join(e["extensions"][:6])
        if len(e["extensions"]) > 6:
            exts += ", ..."
        print(f"{e['name']:<14} {status:<9} {bbox:>4} {conf:>4} {tbl:>4} {img:>4}  {exts}")


async def _cmd_compare(args) -> None:
    from docfold.engines.base import OutputFormat

    router = _build_router()
    engine_names = args.engines.split(",") if args.engines else None

    results = await router.compare(args.file, OutputFormat.MARKDOWN, engines=engine_names)

    for name, result in results.items():
        print(f"\n{'=' * 60}")
        print(f"Engine: {name} | Time: {result.processing_time_ms}ms | Pages: {result.pages}")
        print(f"{'=' * 60}")
        # Print first 500 chars of content as preview
        preview = result.content[:500]
        if len(result.content) > 500:
            preview += "\n... (truncated)"
        print(preview)


async def _cmd_evaluate(args) -> None:
    from docfold.evaluation.runner import EvaluationRunner

    router = _build_router()
    engine_names = args.engines.split(",") if args.engines else None

    runner = EvaluationRunner(router, dataset_path=args.dataset)
    report = await runner.run(engines=engine_names)

    report_json = report.to_json()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_json)
        print(f"Report written to {args.output}")
    else:
        print(report_json)


if __name__ == "__main__":
    main()

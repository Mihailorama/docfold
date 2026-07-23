"""docfold CLI entry-point."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> None:
    import docfold

    parser = argparse.ArgumentParser(
        prog="docfold",
        description="Turn any document into structured data.",
    )
    parser.add_argument("--version", action="version", version=docfold.__version__)
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

    # --- install ---
    install_p = sub.add_parser("install", help="Register the docfold MCP server in an AI client")
    install_p.add_argument(
        "client",
        nargs="?",
        default="generic",
        help="claude | codex | cursor | vscode | generic (default: generic)",
    )
    install_p.add_argument(
        "--print-only",
        action="store_true",
        help="Show what would be done without executing.",
    )
    install_p.add_argument(
        "--json",
        action="store_true",
        help="Emit the generic mcpServers config JSON and exit.",
    )

    # --- doctor ---
    doctor_p = sub.add_parser("doctor", help="Health check: version, MCP extra, engines")
    doctor_p.add_argument("--json", action="store_true", help="Emit JSON report to stdout.")

    # --- update ---
    update_p = sub.add_parser("update", help="Self-update docfold via PyPI")
    update_p.add_argument(
        "--check",
        action="store_true",
        help="Only check PyPI for a newer version; don't install.",
    )
    update_p.add_argument(
        "--extras",
        help='Comma-separated extras to include in the upgrade (e.g. "mcp,docling").',
    )
    update_p.add_argument("--json", action="store_true", help="Emit JSON (with --check).")

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
    elif args.command == "install":
        _cmd_install(args)
    elif args.command == "doctor":
        _cmd_doctor(args)
    elif args.command == "update":
        _cmd_update(args)


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
        from docfold.engines.easyocr_engine import EasyOCREngine
        router.register(EasyOCREngine())
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
        from docfold.engines.liteparse_engine import LiteParseEngine
        router.register(LiteParseEngine())
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

    try:
        from docfold.engines.chandra_engine import ChandraEngine
        router.register(ChandraEngine())
    except Exception:
        pass

    try:
        from docfold.engines.nougat_engine import NougatEngine
        router.register(NougatEngine())
    except Exception:
        pass

    try:
        from docfold.engines.surya_engine import SuryaEngine
        router.register(SuryaEngine())
    except Exception:
        pass

    try:
        from docfold.engines.unlimited_ocr_engine import UnlimitedOCREngine
        router.register(UnlimitedOCREngine())
    except Exception:
        pass

    try:
        from docfold.engines.firecrawl_engine import FirecrawlEngine
        router.register(FirecrawlEngine())
    except Exception:
        pass
    try:
        from docfold.engines.markitdown_engine import MarkItDownEngine
        router.register(MarkItDownEngine())
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
    from docfold.utils.quality import QualityThresholds, gibberish_ratio, quality_ok

    router = _build_router()
    engine_names = args.engines.split(",") if args.engines else None

    results = await router.compare(args.file, OutputFormat.MARKDOWN, engines=engine_names)

    thresholds = QualityThresholds.from_env()

    # --- Quality summary table ---
    print(f"\n{'=' * 72}")
    print("Quality Check Summary")
    print(f"{'=' * 72}")
    print(
        f"  {'Engine':<16} {'Quality':>8} {'Length':>8} "
        f"{'Gibberish':>10} {'Confidence':>11} {'Time':>8}"
    )
    print(f"  {'-' * 68}")

    for name, result in results.items():
        passed = quality_ok(result, thresholds)
        status = "PASS" if passed else "FAIL"
        length = len(result.content.strip()) if result.content else 0
        gib = gibberish_ratio(result.content) if result.content else 0.0
        conf = f"{result.confidence:.2f}" if result.confidence is not None else "—"
        time_str = f"{result.processing_time_ms}ms"
        print(
            f"  {name:<16} {status:>8} {length:>8} "
            f"{gib:>9.1%} {conf:>11} {time_str:>8}"
        )

    print(f"  {'-' * 68}")
    print(
        f"  Thresholds: min_length={thresholds.min_text_length}, "
        f"max_gibberish={thresholds.gibberish_ratio_max:.0%}, "
        f"min_confidence={thresholds.ocr_confidence_min}"
    )

    # --- Per-engine detailed output ---
    for name, result in results.items():
        passed = quality_ok(result, thresholds)
        quality_tag = " [QUALITY: PASS]" if passed else " [QUALITY: FAIL]"
        print(f"\n{'=' * 60}")
        print(
            f"Engine: {name} | Time: {result.processing_time_ms}ms "
            f"| Pages: {result.pages}{quality_tag}"
        )
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


def _cmd_install(args) -> None:
    import json

    from docfold import install as install_mod

    if args.json:
        print(json.dumps(install_mod.mcp_config(), indent=2))
        return

    try:
        plan = install_mod.plan_install(args.client)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    try:
        print(install_mod.apply_plan(plan, print_only=args.print_only))
    except Exception as exc:
        print(f"install failed for {args.client}: {exc}", file=sys.stderr)
        sys.exit(1)


def _doctor_report() -> dict:
    """Collect the health-check data for ``docfold doctor``."""
    import importlib.util
    import platform

    import docfold

    engines = {
        e["name"]: "ok" if e["available"] else "unavailable (extra not installed)"
        for e in _build_router().list_engines()
    }
    return {
        "version": docfold.__version__,
        "python": platform.python_version(),
        "mcp_extra": importlib.util.find_spec("mcp") is not None,
        "engines": engines,
    }


def _cmd_doctor(args) -> None:
    import json

    report = _doctor_report()

    if args.json:
        print(json.dumps(report))
        return

    print(f"docfold {report['version']} · python {report['python']}")
    if report["mcp_extra"]:
        print("mcp extra: installed (docfold-mcp ready)")
    else:
        print('mcp extra: NOT installed — pip install "docfold[mcp]" for the MCP server')

    ok = [name for name, status in report["engines"].items() if status == "ok"]
    missing = {n: s for n, s in report["engines"].items() if s != "ok"}
    print(f"engines: {len(ok)}/{len(report['engines'])} available")
    for name, status in missing.items():
        print(f"  {name}: {status}")


def _cmd_update(args) -> None:
    import json
    import subprocess

    import docfold
    from docfold import update as update_mod

    current = docfold.__version__

    if args.check:
        try:
            latest = update_mod.latest_version()
        except Exception as exc:
            print(f"update check failed: {exc}", file=sys.stderr)
            sys.exit(1)
        newer = update_mod.is_newer(latest, current)
        if args.json:
            print(json.dumps({"current": current, "latest": latest, "update_available": newer}))
            return
        if newer:
            print(f"update available: {current} → {latest} (run: docfold update)")
        else:
            print(f"up to date: {current}")
        return

    update_argv = update_mod.build_update_argv(args.extras)
    print(f"running: {' '.join(update_argv)}", file=sys.stderr)
    try:
        subprocess.run(update_argv, check=True)
    except Exception as exc:
        print(f"update failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print("updated — run 'docfold doctor' to verify")


if __name__ == "__main__":
    main()

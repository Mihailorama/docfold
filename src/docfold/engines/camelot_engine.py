"""Camelot table extraction: tables with page, bounding box and accuracy.

Install: ``pip install docfold[camelot]``. ``stream`` (default) finds tables
separated by whitespace; ``lattice`` needs ruling lines (and Ghostscript).
"""

from __future__ import annotations

import asyncio
import html
import json
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

_STREAM_DEFAULTS = {"row_tol": 15, "edge_tol": 50}


def _clean(cells: list[list[Any]]) -> list[list[str]]:
    rows = [[str(c).strip() for c in row] for row in cells]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    keep = [i for i in range(len(rows[0])) if any(i < len(r) and r[i] for r in rows)]
    return [[r[i] if i < len(r) else "" for i in keep] for r in rows]


def _records(cells: list[list[str]]) -> list[dict[str, str]]:
    if len(cells) < 2:
        return []
    header = [h or f"column_{i + 1}" for i, h in enumerate(cells[0])]
    return [dict(zip(header, row)) for row in cells[1:]]


class CamelotEngine(DocumentEngine):
    """PDF tables via Camelot. ``content`` holds only the tables.

    ``tables``: ``{"page", "bbox" [x0, y0, x1, y1] (PDF points, top-left origin),
    "accuracy", "cells" (rows of strings), "records" (dicts keyed by the first
    row)}`` per table; each also becomes a ``Table`` entry in ``bounding_boxes``.
    """

    def __init__(self, flavor: str = "stream", pages: str = "all", **camelot_kwargs: Any) -> None:
        self._flavor = flavor
        self._pages = pages
        self._kwargs = {**(_STREAM_DEFAULTS if flavor == "stream" else {}), **camelot_kwargs}

    @property
    def name(self) -> str:
        return "camelot"

    @property
    def supported_extensions(self) -> set[str]:
        return {"pdf"}

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(bounding_boxes=True, confidence=True, table_structure=True)

    def is_available(self) -> bool:
        try:
            import camelot  # noqa: F401
            return True
        except Exception:  # noqa: BLE001 - broken cv2/ghostscript bindings
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()
        tables = await asyncio.get_running_loop().run_in_executor(None, self._extract, file_path)
        if output_format == OutputFormat.JSON:
            content = json.dumps(tables, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            content = "\n".join(_html(t) for t in tables)
        else:
            content = "\n\n".join(_markdown(t) for t in tables)
        accuracies = [t["accuracy"] for t in tables if t["accuracy"] is not None]
        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            tables=tables,
            bounding_boxes=[
                {"type": "Table", "bbox": t["bbox"], "page": t["page"], "id": f"t{i}",
                 "confidence": t["accuracy"], "page_height": t.get("page_height")}
                for i, t in enumerate(tables)
            ],
            confidence=sum(accuracies) / len(accuracies) if accuracies else None,
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={"flavor": self._flavor, "table_count": len(tables)},
        )

    def _extract(self, file_path: str) -> list[dict[str, Any]]:
        import camelot

        found = camelot.read_pdf(file_path, flavor=self._flavor, pages=self._pages, **self._kwargs)
        heights = _page_heights(file_path)
        out = []
        for table in found:
            cells = _clean(table.df.values.tolist())
            if not cells:
                continue
            page = int(table.page)
            x0, y0, x1, y1 = (float(v) for v in table._bbox)  # PDF space, bottom-left origin
            height = heights.get(page)
            bbox = [x0, height - y1, x1, height - y0] if height else [x0, y0, x1, y1]
            accuracy = getattr(table, "accuracy", None)
            out.append({
                "page": page,
                "bbox": [round(v, 2) for v in bbox],
                "page_height": height,
                "accuracy": round(accuracy / 100, 4) if accuracy is not None else None,
                "cells": cells,
                "records": _records(cells),
            })
        return out


def _page_heights(file_path: str) -> dict[int, float]:
    try:
        import pymupdf
    except ImportError:
        return {}
    with pymupdf.open(file_path) as doc:
        return {i + 1: float(p.rect.height) for i, p in enumerate(doc)}


def _markdown(table: dict[str, Any]) -> str:
    cells = table["cells"]
    width = max(len(r) for r in cells)
    rows = [[c.replace("|", "\\|").replace("\n", " ") for c in r] + [""] * (width - len(r))
            for r in cells]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return f"<!-- page {table['page']} -->\n" + "\n".join(lines)


def _html(table: dict[str, Any]) -> str:
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>"
        for row in table["cells"]
    )
    return f"<table data-page=\"{table['page']}\">{body}</table>"

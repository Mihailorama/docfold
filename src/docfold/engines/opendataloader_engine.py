"""OpenDataLoader PDF engine adapter.

Wraps the `opendataloader-pdf <https://github.com/opendataloader-project/opendataloader-pdf>`_
Java tool via its Python package (`opendataloader-pdf` on PyPI).  Produces
Markdown / HTML / JSON output with per-element bounding boxes and PDF page
numbers, fully local, no API keys.

Install: ``pip install docfold[opendataloader]`` (also requires Java 11+).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from typing import Any

from docfold.engines.base import (
    BoundingBox,
    DocumentEngine,
    EngineCapabilities,
    EngineResult,
    OutputFormat,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf"}


# Upstream block type -> docfold canonical type.
_TYPE_MAP: dict[str, str] = {
    "heading": "SectionHeader",
    "title": "SectionHeader",
    "paragraph": "Text",
    "text": "Text",
    "caption": "Caption",
    "table": "Table",
    "table-cell": "TableCell",
    "list": "List",
    "list-item": "ListItem",
    "figure": "Image",
    "image": "Image",
    "header": "PageHeader",
    "footer": "PageFooter",
    "footnote": "Footnote",
}


def _convert(*args: Any, **kwargs: Any) -> None:
    """Indirection so tests can monkey-patch the JAR call."""
    from opendataloader_pdf import convert as _upstream_convert

    _upstream_convert(*args, **kwargs)


def _map_type(raw_type: str) -> str:
    if not raw_type:
        return "Text"
    return _TYPE_MAP.get(raw_type.lower(), raw_type.capitalize())


def _walk_kids(
    nodes: list[dict[str, Any]],
    bboxes: list[dict[str, Any]],
    counter: dict[str, int],
) -> None:
    """Depth-first flatten nested ``kids`` into a list of :class:`BoundingBox` dicts."""
    for node in nodes:
        if not isinstance(node, dict):
            continue

        bbox_raw = node.get("bounding box")
        page = node.get("page number")
        text = (node.get("content") or "").strip()
        children = node.get("kids") or []
        node_type = _map_type(node.get("type", ""))

        # Emit a bbox for any node that has enough geometry info.  We prefer
        # leaf nodes (no children) but also include parent containers that
        # carry usable text of their own and geometry — they'll show as a
        # single block instead of being lost.
        if bbox_raw and page and (not children or text):
            try:
                coords = [float(x) for x in bbox_raw]
            except (TypeError, ValueError):
                coords = None
            if coords and len(coords) == 4:
                idx = counter["n"]
                counter["n"] += 1
                bboxes.append(
                    BoundingBox(
                        type=node_type,
                        bbox=coords,
                        page=int(page),
                        text=text,
                        id=f"p{int(page)}-e{idx}",
                    ).to_dict()
                )

        if children:
            _walk_kids(children, bboxes, counter)


def _find_output_file(output_dir: str, suffixes: tuple[str, ...]) -> str | None:
    for name in sorted(os.listdir(output_dir)):
        for suffix in suffixes:
            if name.endswith(suffix):
                return os.path.join(output_dir, name)
    return None


class OpenDataLoaderEngine(DocumentEngine):
    """Adapter for ``opendataloader-pdf`` (Java CLI via Python wrapper)."""

    def __init__(
        self,
        *,
        reading_order: str | None = None,
        table_method: str | None = None,
        include_header_footer: bool = False,
        keep_line_breaks: bool = False,
        use_struct_tree: bool = False,
        password: str | None = None,
        hybrid: str | None = None,
    ) -> None:
        self._reading_order = reading_order
        self._table_method = table_method
        self._include_header_footer = include_header_footer
        self._keep_line_breaks = keep_line_breaks
        self._use_struct_tree = use_struct_tree
        self._password = password
        self._hybrid = hybrid

    # ------------------------------------------------------------------
    # Engine metadata
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "opendataloader"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=True,
            reading_order=True,
            heading_detection=True,
            table_structure=True,
        )

    def is_available(self) -> bool:
        if shutil.which("java") is None:
            return False
        try:
            import opendataloader_pdf  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()

        loop = asyncio.get_running_loop()
        content, page_count, bboxes = await loop.run_in_executor(
            None, self._run, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=page_count,
            processing_time_ms=elapsed_ms,
            bounding_boxes=bboxes or None,
            metadata={
                "reading_order": self._reading_order or "default",
                "table_method": self._table_method or "default",
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(
        self, file_path: str, output_format: OutputFormat,
    ) -> tuple[str, int, list[dict[str, Any]]]:
        formats = self._formats_for(output_format)

        with tempfile.TemporaryDirectory() as out_dir:
            try:
                _convert(
                    file_path,
                    output_dir=out_dir,
                    format=formats,
                    password=self._password,
                    reading_order=self._reading_order,
                    table_method=self._table_method,
                    include_header_footer=self._include_header_footer,
                    keep_line_breaks=self._keep_line_breaks,
                    use_struct_tree=self._use_struct_tree,
                    hybrid=self._hybrid,
                    quiet=True,
                )
            except Exception as exc:
                raise RuntimeError(f"opendataloader failed: {exc}") from exc

            json_path = _find_output_file(out_dir, (".json",))
            if not json_path:
                raise RuntimeError("opendataloader produced no JSON output")

            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)

            page_count = int(data.get("number of pages", 0) or 0)
            bboxes: list[dict[str, Any]] = []
            _walk_kids(data.get("kids") or [], bboxes, {"n": 0})

            content = self._read_primary(out_dir, output_format, data)

        return content, page_count, bboxes

    @staticmethod
    def _formats_for(output_format: OutputFormat) -> list[str]:
        """Build the list of output formats to request from the JAR."""
        # Always include JSON — it carries the bounding-box tree we need.
        formats = ["json"]
        if output_format == OutputFormat.MARKDOWN:
            formats.append("markdown")
        elif output_format == OutputFormat.HTML:
            formats.append("html")
        elif output_format == OutputFormat.TEXT:
            formats.append("text")
        return formats

    @staticmethod
    def _read_primary(
        out_dir: str, output_format: OutputFormat, json_data: dict[str, Any],
    ) -> str:
        if output_format == OutputFormat.JSON:
            return json.dumps(json_data, ensure_ascii=False)

        suffix_map = {
            OutputFormat.MARKDOWN: (".md",),
            OutputFormat.HTML: (".html",),
            OutputFormat.TEXT: (".txt",),
        }
        path = _find_output_file(out_dir, suffix_map.get(output_format, (".md",)))
        if path is None:
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()

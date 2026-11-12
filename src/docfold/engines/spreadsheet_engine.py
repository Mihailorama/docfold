"""Spreadsheet engine: xlsx/csv/tsv with sheet names and cell coordinates.

Reads values directly (openpyxl for workbooks, the csv module for text), so
every value keeps its origin: ``metadata["cell_map"]`` maps each non-empty
cell to its sheet, A1 coordinate and position in the TSV text.

Install: ``pip install docfold[spreadsheet]`` (CSV/TSV need nothing extra).
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

MAX_CELL_MAP = 200_000
"""Cap on ``cell_map`` entries (memory guard for huge workbooks)."""

_TEXT_EXTENSIONS = {"csv", "tsv"}
_WORKBOOK_EXTENSIONS = {"xlsx", "xlsm"}


def csv_to_records(text: str, delimiter: str | None = None) -> list[dict[str, Any]]:
    """Parse CSV text into row dicts keyed by the header row.

    The delimiter is sniffed from the first 8 KB (``, ; \\t |``) unless given;
    comma when sniffing fails.
    """
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter or _sniff(text)))


def _sniff(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def _column_letter(idx: int) -> str:
    """0-based column index -> Excel letters (0 -> A, 26 -> AA)."""
    letters = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _records(rows: list[Sequence[Any]]) -> list[dict[str, Any]]:
    rows = [r for r in rows if any(v not in (None, "") for v in r)]
    if not rows:
        return []
    header = [
        str(h) if h not in (None, "") else f"column_{i + 1}" for i, h in enumerate(rows[0])
    ]
    return [dict(zip(header, row)) for row in rows[1:]]


class SpreadsheetEngine(DocumentEngine):
    """xlsx / xlsm / csv / tsv reader that keeps sheet + cell provenance.

    Output by ``output_format``:

    - ``JSON``: records. CSV/TSV -> ``[{header: value}]``; workbooks ->
      ``{sheet: [{header: value}]}`` (first non-empty row is the header).
    - anything else: workbooks -> TSV per sheet (``Sheet: <name>`` line before
      each sheet when there are several), ``format=TEXT``; CSV/TSV -> the file
      text unchanged.

    ``metadata``: ``sheets`` (names), ``cell_map`` (``sheet``, ``cell``,
    ``tsv_row``, ``tsv_col``, ``value`` truncated to 100 chars, one per
    non-empty cell; ``tsv_row`` counts rows across all sheets) and
    ``cell_map_truncated``.
    """

    @property
    def name(self) -> str:
        return "spreadsheet"

    @property
    def supported_extensions(self) -> set[str]:
        return _WORKBOOK_EXTENSIONS | _TEXT_EXTENSIONS

    def is_available(self) -> bool:
        try:
            import openpyxl  # noqa: F401
            return True
        except ImportError:
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._read, file_path, output_format)
        result.processing_time_ms = int((time.perf_counter() - start) * 1000)
        return result

    def _read(self, file_path: str, output_format: OutputFormat) -> EngineResult:
        path = Path(file_path)
        ext = path.suffix.lstrip(".").lower()
        sheets: list[tuple[str, list[Sequence[Any]]]]
        if ext in _TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8-sig")
            delimiter = "\t" if ext == "tsv" else _sniff(text)
            sheets = [(path.stem, list(csv.reader(io.StringIO(text), delimiter=delimiter)))]
        else:
            import openpyxl

            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            try:
                sheets = [
                    (ws.title, list(ws.iter_rows(values_only=True))) for ws in wb.worksheets
                ]
            finally:
                wb.close()

        cell_map, truncated = self._cell_map(sheets)
        if output_format == OutputFormat.JSON:
            if ext in _TEXT_EXTENSIONS:
                payload: Any = csv_to_records(text, delimiter=delimiter)
            else:
                payload = {name: _records(rows) for name, rows in sheets}
            content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
            fmt = OutputFormat.JSON
        elif ext in _TEXT_EXTENSIONS:
            content, fmt = text, OutputFormat.TEXT
        else:
            content, fmt = self._tsv(sheets), OutputFormat.TEXT

        return EngineResult(
            content=content,
            format=fmt,
            engine_name=self.name,
            metadata={
                "sheets": [name for name, _ in sheets],
                "cell_map": cell_map,
                "cell_map_truncated": truncated,
            },
        )

    @staticmethod
    def _tsv(sheets: list[tuple[str, list[Sequence[Any]]]]) -> str:
        blocks = []
        for name, rows in sheets:
            if not rows:
                continue
            body = "\n".join(
                "\t".join("" if v is None else str(v) for v in row) for row in rows
            )
            blocks.append(f"Sheet: {name}\n{body}" if len(sheets) > 1 else body)
        return "\n\n".join(blocks)

    @staticmethod
    def _cell_map(
        sheets: Iterable[tuple[str, list[Sequence[Any]]]],
    ) -> tuple[list[dict[str, Any]], bool]:
        cell_map: list[dict[str, Any]] = []
        tsv_row = 0
        for name, rows in sheets:
            for row_idx, row in enumerate(rows, start=1):
                for col_idx, value in enumerate(row):
                    if value is None or value == "":
                        continue
                    if len(cell_map) >= MAX_CELL_MAP:
                        return cell_map, True
                    cell_map.append({
                        "tsv_row": tsv_row,
                        "tsv_col": col_idx,
                        "sheet": name,
                        "cell": f"{_column_letter(col_idx)}{row_idx}",
                        "value": str(value)[:100],
                    })
                tsv_row += 1
        return cell_map, False

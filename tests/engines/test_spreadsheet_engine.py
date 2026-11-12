"""SpreadsheetEngine: sheet names, cell coordinates, records (DOCFOLD-15)."""

from __future__ import annotations

import json

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.spreadsheet_engine import SpreadsheetEngine, csv_to_records

openpyxl = pytest.importorskip("openpyxl")


def _xlsx(path, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    wb.save(path)
    return str(path)


@pytest.fixture
def engine():
    return SpreadsheetEngine()


async def test_multi_sheet_text_and_cell_map(engine, tmp_path):
    path = _xlsx(tmp_path / "book.xlsx", {
        "Orders": [["id", "total"], [1, 9.5], [2, None]],
        "Clients": [["name"], ["Acme"]],
    })
    res = await engine.process(path, output_format=OutputFormat.MARKDOWN)
    assert res.engine_name == "spreadsheet"
    assert res.content == "Sheet: Orders\nid\ttotal\n1\t9.5\n2\t\n\nSheet: Clients\nname\nAcme"
    assert res.metadata["sheets"] == ["Orders", "Clients"]
    cm = res.metadata["cell_map"]
    assert cm[0] == {"tsv_row": 0, "tsv_col": 0, "sheet": "Orders", "cell": "A1", "value": "id"}
    assert {"tsv_row": 1, "tsv_col": 1, "sheet": "Orders", "cell": "B2", "value": "9.5"} in cm
    # empty cell B3 is not mapped; tsv_row counts rows across sheets
    assert not any(c["sheet"] == "Orders" and c["cell"] == "B3" for c in cm)
    assert {"tsv_row": 4, "tsv_col": 0, "sheet": "Clients", "cell": "A2", "value": "Acme"} in cm
    assert res.metadata["cell_map_truncated"] is False


async def test_single_sheet_has_no_header(engine, tmp_path):
    path = _xlsx(tmp_path / "one.xlsx", {"Data": [["a", "b"], ["x" * 150, 2]]})
    res = await engine.process(path, output_format=OutputFormat.TEXT)
    assert res.content.startswith("a\tb\n")
    assert res.metadata["cell_map"][2]["value"] == "x" * 100


async def test_xlsx_json_records(engine, tmp_path):
    path = _xlsx(tmp_path / "r.xlsx", {"S": [["id", None], [1, "v"], [None, None]]})
    res = await engine.process(path, output_format=OutputFormat.JSON)
    assert res.format == OutputFormat.JSON
    assert json.loads(res.content) == {"S": [{"id": 1, "column_2": "v"}]}


async def test_csv_records_and_cell_map(engine, tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("name;city\nАнна;Москва\nBob;Paris\n", encoding="utf-8")
    res = await engine.process(str(path), output_format=OutputFormat.JSON)
    assert json.loads(res.content) == [
        {"name": "Анна", "city": "Москва"}, {"name": "Bob", "city": "Paris"},
    ]
    assert {"tsv_row": 2, "tsv_col": 1, "sheet": "data", "cell": "B3", "value": "Paris"} in (
        res.metadata["cell_map"]
    )
    text = await engine.process(str(path), output_format=OutputFormat.MARKDOWN)
    assert text.content == "name;city\nАнна;Москва\nBob;Paris\n"


async def test_tsv_records(engine, tmp_path):
    path = tmp_path / "t.tsv"
    path.write_text("a\tb\n1\t2\n", encoding="utf-8")
    res = await engine.process(str(path), output_format=OutputFormat.JSON)
    assert json.loads(res.content) == [{"a": "1", "b": "2"}]


def test_csv_to_records_sniffs_delimiter():
    assert csv_to_records("a|b\n1|2\n") == [{"a": "1", "b": "2"}]
    assert csv_to_records("single\nvalue\n") == [{"single": "value"}]


async def test_cell_map_cap(tmp_path, monkeypatch):
    import docfold.engines.spreadsheet_engine as se

    monkeypatch.setattr(se, "MAX_CELL_MAP", 3)
    path = _xlsx(tmp_path / "big.xlsx", {"S": [[1, 2], [3, 4]]})
    res = await SpreadsheetEngine().process(path)
    assert len(res.metadata["cell_map"]) == 3
    assert res.metadata["cell_map_truncated"] is True


def test_available_and_extensions(engine):
    assert engine.is_available()
    assert {"xlsx", "csv", "tsv"} <= engine.supported_extensions

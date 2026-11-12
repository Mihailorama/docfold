"""PDF unlock and Camelot tables (DOCFOLD-20)."""

from __future__ import annotations

import json
import sys
import types

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.camelot_engine import CamelotEngine
from docfold.preprocessing import unlock

pymupdf = pytest.importorskip("pymupdf")


def _pdf(path, **save):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Secret text")
    doc.save(path, **save)
    doc.close()
    return str(path)


@pytest.fixture(params=["pymupdf", "qpdf"])
def via(request, monkeypatch):
    if request.param == "pymupdf":
        monkeypatch.setattr(unlock.shutil, "which", lambda name: None)
    elif not unlock.shutil.which("qpdf"):
        pytest.skip("qpdf not installed")
    return request.param


def test_plain_pdf_untouched(tmp_path, via):
    path = _pdf(tmp_path / "a.pdf")
    assert unlock.unlock_pdf(path) == path


def test_owner_password_removed(tmp_path, via):
    path = _pdf(tmp_path / "o.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="own",
                permissions=0)
    out = unlock.unlock_pdf(path)
    assert out.endswith("o_unlocked.pdf")
    assert not unlock.is_protected(out)
    with pymupdf.open(out) as doc:
        assert "Secret text" in doc[0].get_text()


def test_user_password(tmp_path, via):
    path = _pdf(tmp_path / "u.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o",
                user_pw="pw")
    with pytest.raises(ValueError):
        unlock.unlock_pdf(path, out_path=str(tmp_path / "x.pdf"))
    out = unlock.unlock_pdf(path, out_path=str(tmp_path / "ok.pdf"), password="pw")
    assert out == str(tmp_path / "ok.pdf") and not unlock.is_protected(out)


class _FakeTable:
    def __init__(self, page, bbox, accuracy, rows):
        self.page, self._bbox, self.accuracy = str(page), bbox, accuracy
        self.df = types.SimpleNamespace(values=types.SimpleNamespace(tolist=lambda: rows))


async def test_camelot_engine_with_fake(tmp_path, monkeypatch):
    path = _pdf(tmp_path / "t.pdf")  # 842 pt high A4 page
    rows = [["Item", "", "Qty"], ["Bolt", "", "4"], ["", "", ""], ["Nut", "", "10"]]
    fake = types.ModuleType("camelot")
    fake.read_pdf = lambda *a, **k: [_FakeTable(1, (50, 700, 300, 800), 97.5, rows)]
    monkeypatch.setitem(sys.modules, "camelot", fake)
    eng = CamelotEngine()
    assert eng.is_available()
    res = await eng.process(path, output_format=OutputFormat.JSON)
    t = res.tables[0]
    assert t["cells"] == [["Item", "Qty"], ["Bolt", "4"], ["Nut", "10"]]
    assert t["records"] == [{"Item": "Bolt", "Qty": "4"}, {"Item": "Nut", "Qty": "10"}]
    assert t["page"] == 1 and t["accuracy"] == 0.975
    assert t["bbox"] == [50.0, 42.0, 300.0, 142.0]  # flipped to top-left origin
    assert res.bounding_boxes[0]["type"] == "Table"
    assert json.loads(res.content)[0]["records"][1]["Item"] == "Nut"
    md = await eng.process(path)
    assert "| Item | Qty |" in md.content and "| Nut | 10 |" in md.content


async def test_camelot_real(tmp_path):
    pytest.importorskip("camelot")
    doc = pymupdf.open()
    page = doc.new_page()
    data = [("Product", "Units", "Price"), ("Carretera", "1618", "20"),
            ("Montana", "1321", "15"), ("Paseo", "2178", "350"), ("Velo", "888", "120")]
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            page.insert_text((72 + c * 140, 120 + r * 22), val, fontsize=11)
    path = tmp_path / "table.pdf"
    doc.save(path)
    doc.close()
    res = await CamelotEngine().process(str(path))
    assert res.tables, "no table found"
    cells = res.tables[0]["cells"]
    assert ["Montana", "1321", "15"] in cells

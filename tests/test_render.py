"""render_pages: public page-image rendering (DOCFOLD-14)."""

from __future__ import annotations

import pytest

from docfold import render

pymupdf = pytest.importorskip("pymupdf")


def _pdf(path, n=3):
    doc = pymupdf.open()
    for i in range(n):
        page = doc.new_page(width=200, height=100)
        page.insert_text((20, 50), f"page {i + 1}")
    doc.save(path)
    doc.close()
    return str(path)


def test_all_pages_png(tmp_path):
    out = list(render.render_pages(_pdf(tmp_path / "a.pdf")))
    assert [n for n, _ in out] == [1, 2, 3]
    assert all(b.startswith(b"\x89PNG") for _, b in out)


def test_page_subset(tmp_path):
    path = _pdf(tmp_path / "a.pdf", 5)
    assert [n for n, _ in render.render_pages(path, "2-3,5,9")] == [2, 3, 5]
    assert [n for n, _ in render.render_pages(path, [4, 1, 99])] == [4, 1]


def test_jpeg_quality_and_size(tmp_path):
    path = _pdf(tmp_path / "a.pdf", 1)
    hi = next(render.render_pages(path, image_format="jpeg", quality=95))[1]
    lo = next(render.render_pages(path, image_format="jpeg", quality=20))[1]
    assert hi.startswith(b"\xff\xd8") and lo.startswith(b"\xff\xd8")
    assert len(lo) < len(hi)


def test_webp(tmp_path):
    pytest.importorskip("PIL")
    data = next(render.render_pages(_pdf(tmp_path / "a.pdf", 1), image_format="webp"))[1]
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def test_dpi(tmp_path):
    path = _pdf(tmp_path / "a.pdf", 1)
    small = pymupdf.Pixmap(next(render.render_pages(path, dpi=72))[1])
    big = pymupdf.Pixmap(next(render.render_pages(path, dpi=144))[1])
    assert (small.width, big.width) == (200, 400)


def test_image_input(tmp_path):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 40), 0)
    pix.clear_with(255)
    img = tmp_path / "scan.png"
    pix.save(img)
    out = list(render.render_pages(str(img)))
    assert [n for n, _ in out] == [1]


def test_bad_format(tmp_path):
    with pytest.raises(ValueError, match="image_format"):
        next(render.render_pages(_pdf(tmp_path / "a.pdf", 1), image_format="gif"))


def test_office_without_libreoffice(tmp_path, monkeypatch):
    monkeypatch.setattr(render.shutil, "which", lambda name: None)
    doc = tmp_path / "memo.docx"
    doc.write_bytes(b"PK")
    with pytest.raises(RuntimeError, match="LibreOffice"):
        next(render.render_pages(str(doc)))


def test_lazy(tmp_path):
    gen = render.render_pages(str(tmp_path / "missing.pdf"))
    with pytest.raises(Exception):
        next(gen)

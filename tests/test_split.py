"""docfold.split: one PDF holding several documents -> one page range per document."""

import hashlib
import json
import types

import pytest

pymupdf = pytest.importorskip("pymupdf")

from docfold import split as ds  # noqa: E402

TYPES = [
    "КС-2 (акт о приемке выполненных работ)",
    "КС-3 (справка о стоимости выполненных работ и затрат)",
]
KS2, KS3 = TYPES


def _pdf(path, pages):
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            # Helvetica has no Cyrillic glyphs; a built-in CJK font does.
            page.insert_text((72, 72), text, fontname="china-s")
    doc.save(path)
    return str(path)


def _answer(entries):
    content = json.dumps({"pages": entries}, ensure_ascii=False)
    message = types.SimpleNamespace(content=content)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def test_cut_pages_keeps_range_and_is_deterministic(tmp_path):
    src = _pdf(tmp_path / "a.pdf", [f"page {i}" for i in range(1, 7)])
    hashes = []
    for name in ("b.pdf", "c.pdf"):
        dst = tmp_path / name
        dst.write_bytes(open(src, "rb").read())
        assert ds.cut_pages(str(dst), "2-4") == 3
        hashes.append(hashlib.sha256(dst.read_bytes()).hexdigest())
        with pymupdf.open(dst) as doc:
            assert [p.get_text().strip() for p in doc] == ["page 2", "page 3", "page 4"]
    assert hashes[0] == hashes[1]
    with pytest.raises(ValueError):
        ds.cut_pages(str(tmp_path / "b.pdf"), "40-41")


def test_titles_split_documents_and_running_headers_do_not():
    # Labels as a free vision model returned them for a 26-page КС-2/КС-3 merge (noisy "new").
    labels = {
        1: {"title": "АКТ О ПРИЕМКЕ ВЫПОЛНЕННЫХ РАБОТ за Июнь 2021 г.", "new": True, "type": KS2},
        2: {"title": "Раздел 2. Система отопления", "new": False, "type": "other"},
        3: {"title": "ГРАНД-Смета 2020", "new": True, "type": "other"},
        4: {"title": "ГРАНД-Смета 2020", "new": True, "type": "other"},
        5: {"title": "Унифицированная форма № КС-2", "printed_page": 1, "new": True, "type": KS2},
        6: {"title": "ГРАНД-Смета 2020", "printed_page": 2, "new": True, "type": "other"},
        7: {"title": "СПРАВКА СТОИМОСТИ ВЫПОЛНЕННЫХ РАБОТ И ЗАТРАТ", "new": True, "type": KS3},
        8: {"title": "Спецификация № 1", "new": True, "type": "other"},
        9: {"title": "", "new": False, "type": "other"},
        10: {"title": "СПРАВКА СТОИМОСТИ ВЫПОЛНЕННЫХ РАБОТ И ЗАТРАТ", "new": False,
             "type": "other"},
    }
    docs = ds.group_pages(labels, 10, TYPES)
    assert [(d.type, d.pages) for d in docs] == [
        (KS2, "1-4"), (KS2, "5-6"), (KS3, "7-7"), ("other", "8-9"), (KS3, "10-10"),
    ]


def test_short_type_names_match_whole_words_only():
    labels = {
        1: {"title": "Счет на оплату № 5"},
        2: {"title": "УПД № 7"},
        3: {"title": "Контакты"},
        4: {"title": "Акт № 3"},
    }
    docs = ds.group_pages(labels, 4, ["Счет на оплату", "УПД", "Акт"])
    assert [(d.type, d.pages) for d in docs] == [
        ("Счет на оплату", "1-1"), ("УПД", "2-3"), ("Акт", "4-4"),
    ]


def test_title_naming_two_types_keeps_the_model_type():
    names = ["УПД (универсальный передаточный документ)", "Счет-фактура"]
    labels = {
        1: {"title": "УПД Счет-фактура № 179", "type": names[0], "new": True},
        2: {"title": "Счет-фактура № 5", "type": names[1], "new": True},
    }
    assert [d.type for d in ds.group_pages(labels, 2, names)] == names


async def test_llm_text_pages_go_in_one_call_scans_one_image_per_call(tmp_path):
    src = _pdf(tmp_path / "k.pdf", [
        "Унифицированная форма № КС-2 АКТ О ПРИЕМКЕ ВЫПОЛНЕННЫХ РАБОТ № 5",
        "продолжение таблицы работ строки 10-20 итого по акту за отчетный период",
        "",  # a scanned page: no text layer
    ])
    calls = []

    async def fake_completion(**kwargs):
        parts = kwargs["messages"][1]["content"][1:]
        calls.append(([p["type"] for p in parts], kwargs["model"], kwargs.get("api_key")))
        if parts[-1]["type"] == "image_url":
            return _answer([{"page": 3, "title": "Справка о стоимости выполненных работ и затрат",
                             "new": True}])
        return _answer([
            {"page": 1, "title": "АКТ О ПРИЕМКЕ ВЫПОЛНЕННЫХ РАБОТ № 5", "new": True,
             "type": "other"},
            {"page": 2, "title": "", "new": False, "type": "other"},
        ])

    llm = ds.LLMPageClassifier(models=[{"model": "vendor/vl", "api_key": "k"}],
                               acompletion=fake_completion)
    result = await ds.split_document(src, TYPES, [llm])
    assert result.method == "llm" and result.pages == 3
    assert [(d.type, d.pages) for d in result.documents] == [(KS2, "1-2"), (KS3, "3-3")]
    assert sorted(c[0] for c in calls) == [["text", "image_url"], ["text", "text"]]
    assert {(c[1], c[2]) for c in calls} == {("vendor/vl", "k")}
    assert result.to_dict()["documents"][0] == {"type": KS2, "start": 1, "end": 2, "pages": "1-2"}


async def test_llm_fallback_chain_moves_to_the_next_model(tmp_path):
    src = _pdf(tmp_path / "k.pdf", ["", ""])  # two scanned pages
    used = []

    async def fake_completion(**kwargs):
        used.append(kwargs["model"])
        if kwargs["model"] == "first/vl":
            raise RuntimeError("provider down")
        page = int(kwargs["messages"][1]["content"][1]["text"].split()[2])
        return _answer([{"page": page, "title": f"Акт № {page}", "new": True}])

    llm = ds.LLMPageClassifier(
        models=["text/only-model", "first/vl", "second/vl"],
        vision=lambda m: m != "text/only-model",
        acompletion=fake_completion,
    )
    result = await ds.split_document(src, ["Акт"], [llm])
    assert result.method == "llm"
    assert [d.pages for d in result.documents] == ["1-1", "2-2"]
    assert "text/only-model" not in used  # a scan never goes to a text-only model
    assert used.count("first/vl") == 2 and used.count("second/vl") == 2


async def test_rate_limited_model_is_retried_before_falling_back(tmp_path):
    src = _pdf(tmp_path / "k.pdf", ["", ""])
    attempts = []

    async def flaky(**kwargs):
        attempts.append(kwargs["model"])
        if len(attempts) == 1:
            raise RuntimeError("429 Too Many Requests")
        page = int(kwargs["messages"][1]["content"][1]["text"].split()[2])
        return _answer([{"page": page, "title": f"Акт № {page}", "new": True}])

    llm = ds.LLMPageClassifier(models=["a/vl", "b/vl"], acompletion=flaky, rate_limit_wait=0,
                               concurrency=1)
    result = await ds.split_document(src, ["Акт"], [llm])
    assert result.method == "llm" and attempts.count("b/vl") == 0


async def test_heuristic_splits_a_text_pdf_without_a_model(tmp_path):
    src = _pdf(tmp_path / "k.pdf", [
        "ООО Ромашка БИК 044525104 Счет на оплату № 134 от 01 октября 2025 г. Поставщик",
        "Акт сдачи-приемки оказанных услуг № 2 от 30 декабря 2025 г. Заказчик и Исполнитель",
        "УПД Счет-фактура № 179 от 30.12.2025 Продавец ООО Ромашка Адрес Ростов",
        "Всего к оплате 228 800,00 Руководитель организации Подпись Основания передачи",
        "Форма по ОКУД 0322005 Унифицированная форма акт за июнь 2021 года объект",
    ])
    names = ["Счет на оплату", "Акт (акт выполненных работ)", "УПД", "Счет-фактура", "КС-2"]
    result = await ds.split_document(src, names, [ds.TextPageClassifier()])
    assert result.method == "heuristic"
    assert [(d.type, d.pages) for d in result.documents] == [
        ("Счет на оплату", "1-1"), ("Акт (акт выполненных работ)", "2-2"),
        ("УПД", "3-4"), ("КС-2", "5-5"),
    ]


async def test_heuristic_abstains_on_scans_and_the_chain_falls_through(tmp_path):
    src = _pdf(tmp_path / "k.pdf", ["Акт № 1 от 01.01.2026 оказанных услуг по договору", ""])

    async def fake_completion(**kwargs):
        page = int(kwargs["messages"][1]["content"][1]["text"].split()[2])
        return _answer([{"page": page, "title": f"Акт № {page}", "new": True}])

    chain = [ds.TextPageClassifier(), ds.LLMPageClassifier(models=["a/vl"],
                                                           acompletion=fake_completion)]
    result = await ds.split_document(src, ["Акт"], chain)
    assert result.method == "llm"
    assert [d.pages for d in result.documents] == ["1-1", "2-2"]


async def test_single_page_no_types_and_failures_read_the_file_whole(tmp_path):
    one = _pdf(tmp_path / "one.pdf", ["only page"])
    two = _pdf(tmp_path / "two.pdf", ["", ""])

    async def broken(**kwargs):
        raise RuntimeError("provider down")

    vl = [ds.LLMPageClassifier(models=["a/vl"], acompletion=broken)]
    assert (await ds.split_document(one, TYPES, vl)).method == "single"
    assert (await ds.split_document(two, [], vl)).method == "single"
    assert (await ds.split_document(str(tmp_path / "missing.pdf"), TYPES, vl)).method == "single"
    failed = await ds.split_document(two, TYPES, vl)
    assert failed.method == "fallback" and "provider down" in (failed.error or "")
    assert failed.to_dict()["documents"] == [{"type": None, "start": 1, "end": 2, "pages": "1-2"}]
    text_only = [ds.LLMPageClassifier(models=["t/only"], vision=lambda m: False,
                                      acompletion=broken)]
    assert (await ds.split_document(two, TYPES, text_only)).method == "no_vision"
    assert (await ds.split_document(two, TYPES, vl, max_pages=1)).method == "too_long"

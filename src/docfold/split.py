"""Split one PDF holding several documents into page ranges, one per document.

Requires ``pip install docfold[split]`` (PyMuPDF); the default LLM call needs
``docfold[split-llm]`` (LiteLLM) unless you pass your own ``acompletion``.

A user may upload one PDF or scan holding several documents (four acceptance acts, a cost
certificate and a specification; an invoice, an act and a UPD). ``split_document`` labels
every page (title, printed page number, document type, "starts a new document") with the
first page classifier that does not abstain, then groups pages into documents by their
titles (``group_pages``)::

    from docfold.split import LLMPageClassifier, TextPageClassifier, split_document

    result = await split_document("merged.pdf", ["Invoice", "Act"], [
        TextPageClassifier(),                       # text layer, no model
        LLMPageClassifier(models=["anthropic/claude-haiku-5-5", "gemini/gemini-3.8-flash"]),
    ])
    result.to_dict()  # {"pages": 26, "documents": [{"type", "start", "end", "pages"}], "method"}

``cut_pages`` rewrites a PDF to one page range so extraction reads one document.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

OTHER = "other"
MIN_TEXT_CHARS = 40
"""A page with less text than this is treated as a scan."""
MAX_SPLIT_PAGES = 60
"""Longer files are returned whole (a 300-page scan would take 300 vision calls)."""

Label = dict[str, Any]
"""One page's label: ``{"page", "title", "printed_page", "type", "new"}``."""


class Abstain(Exception):  # noqa: N818 (a signal, not an error)
    """A classifier cannot label this file; the next classifier in the chain runs.

    ``str(exc)`` is the reason reported as ``method`` when no classifier labels the file.
    """


@dataclass
class SplitDocument:
    type: str | None
    start: int
    end: int

    @property
    def pages(self) -> str:
        return f"{self.start}-{self.end}"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "start": self.start, "end": self.end, "pages": self.pages}


@dataclass
class SplitResult:
    pages: int
    documents: list[SplitDocument]
    method: str
    """Classifier name ("heuristic", "llm"), or why the file is one document: "single",
    "too_long", "no_vision" (scans and no vision model), "fallback" (classifier failed)."""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "pages": self.pages,
            "documents": [d.to_dict() for d in self.documents],
            "method": self.method,
        }
        if self.error:
            out["error"] = self.error
        return out


# --------------------------------------------------------------------------- pages


def _page_ranges(spec: str, page_count: int) -> list[int]:
    """'5-7,9' -> zero-based [4, 5, 6, 8]; pages outside the file are dropped."""
    pages: list[int] = []
    for part in str(spec or "").split(","):
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not m:
            continue
        start = int(m.group(1))
        end = int(m.group(2) or start)
        pages.extend(p - 1 for p in range(start, end + 1) if 1 <= p <= page_count)
    return pages


def cut_pages(file_path: str, spec: str) -> int:
    """Rewrite the PDF at *file_path* in place to the pages in *spec* (1-based, '5-7').

    Same input and range give the same bytes, so a cache keyed by file hash (e.g. OCR)
    serves every reader of this document. Returns the kept page count.
    """
    import pymupdf

    with pymupdf.open(file_path) as doc:
        pages = _page_ranges(spec, doc.page_count)
        if not pages:
            raise ValueError(f"pages '{spec}' are outside the {doc.page_count}-page file")
        if len(pages) == doc.page_count:
            return len(pages)
        doc.select(pages)
        data = doc.tobytes(garbage=3, deflate=True, no_new_id=True)
    with open(file_path, "wb") as fh:
        fh.write(data)
    return len(pages)


def _page_text(page: Any) -> str:
    return " ".join(page.get_text().split())


# --------------------------------------------------------------------------- grouping


def _norm(text: Any) -> str:
    return " ".join(str(text or "").casefold().replace("ё", "е").split())


def _type_aliases(types: Sequence[str]) -> dict[str, str]:
    """'КС-2 (акт о приемке выполненных работ)' is found in a title as the whole name, as
    'КС-2' or as 'акт о приемке выполненных работ'."""
    aliases: dict[str, str] = {}
    for t in types:
        m = re.fullmatch(r"\s*(.*?)\s*\((.*)\)\s*", t)
        for alias in (t, *(m.groups() if m else ())):
            if alias.strip():
                aliases[_norm(alias)] = t
    return aliases


def _named_type(title: str, aliases: dict[str, str], preferred: str | None = None) -> str | None:
    """The type a page title names: an alias found in it verbatim, or a multi-word alias all
    of whose words (3+ letters) are in it ('справка стоимости выполненных работ и затрат'
    names 'справка о стоимости выполненных работ и затрат'). A title naming several types
    ('УПД Счет-фактура № 179') keeps the classifier's type (*preferred*) when it is one."""
    words = set(re.findall(r"[\w-]+", title))
    named: list[str] = []
    for alias in sorted(aliases, key=len, reverse=True):
        alias_words = [w for w in re.findall(r"[\w-]+", alias) if len(w) >= 3]
        verbatim = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", title)
        if verbatim or (len(alias_words) >= 2 and set(alias_words) <= words):
            named.append(aliases[alias])
    if preferred in named:
        return preferred
    return named[0] if named else None


def group_pages(
    labels: dict[int, Label], page_count: int, types: Sequence[str]
) -> list[SplitDocument]:
    """Per-page labels -> consecutive documents.

    Page titles are what vision models read reliably; their "new" flag is noisy. So a
    document starts on a page whose title names a known type, or whose own title (one not
    repeated on other pages, i.e. not a running header) is marked new, and never on a page
    printing a page number above 1. Other pages continue the previous document, whose type
    comes from its first page.
    """
    known = {_norm(t): t for t in types}
    aliases = _type_aliases(types)
    seen: dict[str, int] = {}
    for label in labels.values():
        if title := _norm(label.get("title")):
            seen[title] = seen.get(title, 0) + 1
    documents: list[SplitDocument] = []
    for number in range(1, page_count + 1):
        label = labels.get(number) or {}
        title = _norm(label.get("title"))
        labelled = known.get(_norm(label.get("type")))
        named = _named_type(title, aliases, labelled)
        printed = label.get("printed_page")
        continues = isinstance(printed, int) and printed > 1
        own_title = bool(title) and seen.get(title, 0) == 1 and bool(label.get("new"))
        if not documents or (not continues and (named or own_title)):
            documents.append(SplitDocument(named or labelled or OTHER, number, number))
        else:
            documents[-1].end = number
    return documents


# --------------------------------------------------------------------------- classifiers


class TextPageClassifier:
    """Labels text-layer pages without a model.

    A page starts a document when its head names a type followed by a number sign
    ("Счет-фактура № 179", "Invoice No. 12") or carries an OKUD form code of one of the
    types. Abstains on scans and when the first page has no such title: the next
    classifier (usually an LLM) decides then.
    """

    name = "heuristic"
    OKUD = {"0322005": "кс-2", "0322001": "кс-3", "0330202": "торг-12", "0315001": "м-15"}
    """Russian unified form codes -> the short form name a type may contain."""

    def __init__(self, head_chars: int = 600, min_text_chars: int = MIN_TEXT_CHARS):
        self.head_chars = head_chars
        self.min_text_chars = min_text_chars

    async def label(self, doc: Any, types: Sequence[str]) -> dict[int, Label]:
        texts = [_page_text(page) for page in doc]
        if any(len(t) < self.min_text_chars for t in texts):
            raise Abstain("no_text")
        aliases = _type_aliases(types)
        labels: dict[int, Label] = {}
        for number, text in enumerate(texts, 1):
            head = _norm(text[: self.head_chars])
            title, doc_type = self._title(head, aliases)
            labels[number] = {"page": number, "title": title, "type": doc_type,
                              "printed_page": self._printed_page(_norm(text))}
        if not labels[1]["title"]:
            raise Abstain("no_title")
        return labels

    def _title(self, head: str, aliases: dict[str, str]) -> tuple[str, str | None]:
        """(title, type) of the first type name followed by a number sign in *head*."""
        hits = []
        for alias, doc_type in aliases.items():
            m = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)[^№\n]{{0,60}}?(№|no\.|n°)", head)
            if m:
                hits.append((m.start(), -len(alias), head[m.start(): m.end()], doc_type))
        for code, short in self.OKUD.items():
            if re.search(rf"окуд\D{{0,10}}{code}", head) and short in aliases:
                hits.append((len(head), 0, short, aliases[short]))
        return min(hits)[2:] if hits else ("", None)

    @staticmethod
    def _printed_page(text: str) -> int | None:
        m = re.search(r"(?:страница|стр\.|лист|page)\s*(\d{1,3})(?:\s*(?:из|of)\s*\d+)?", text)
        return int(m.group(1)) if m else None


_SYSTEM = (
    "You split a multi-page file into the separate documents it contains. Pages are given in "
    "order; scanned pages may be rotated or upside down, read them anyway. For every page "
    "report: the title of the document or form that starts on it (its name in the header, "
    "e.g. a form name and number; not a running header or the name of the program that "
    "printed it; empty for a page that continues a document), the page number printed on it "
    "(null if none), its document type, and whether a NEW document starts on it. A new "
    "document starts on a page with its "
    "own title or header block (form name, document number, date, parties) or printed page "
    "number 1, even if the previous document has the same type. A page continuing a table, "
    "totals or signatures of the previous page is not a new document. Answer with JSON only."
)

Completion = Callable[..., Awaitable[Any]]


def _parse_json(content: str) -> Any:
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the answer")
    return json.loads(content[start: end + 1])


def _is_rate_limit(exc: Exception) -> bool:
    return "429" in str(exc) or "rate" in str(exc).lower()


class LLMPageClassifier:
    """Labels pages with a chat model; text pages are batched, scans go one image per call
    (free vision models misread several page images sent together).

    *models* is an ordered fallback chain: LiteLLM model names or kwargs dicts
    (``{"model": "gemini/gemini-3.8-flash", "api_key": "...", "vision": False}``; every key
    but ``vision`` is passed to the call). A call that fails (after *rate_limit_retries*
    waits on HTTP 429) moves to the next model. Text-only models (``vision`` false, or
    *vision(model)* false) are skipped for scanned pages. *acompletion* defaults to
    ``litellm.acompletion``; pass your own gateway to add logging, cost or limits.
    """

    name = "llm"

    def __init__(
        self,
        models: Sequence[str | dict[str, Any]],
        *,
        acompletion: Completion | None = None,
        vision: Callable[[str], bool] | None = None,
        text_pages_per_call: int = 30,
        concurrency: int = 4,
        image_dpi: int = 150,
        timeout: float = 300,
        rate_limit_retries: int = 3,
        rate_limit_wait: float = 15,
        min_text_chars: int = MIN_TEXT_CHARS,
    ):
        if not models:
            raise ValueError("LLMPageClassifier needs at least one model")
        self.models: list[dict[str, Any]] = []
        for m in models:
            entry: dict[str, Any] = {"model": m} if isinstance(m, str) else dict(m)
            if "vision" not in entry:
                entry["vision"] = vision(entry["model"]) if vision else True
            self.models.append(entry)
        self._acompletion = acompletion
        self.text_pages_per_call = text_pages_per_call
        self.concurrency = concurrency
        self.image_dpi = image_dpi
        self.timeout = timeout
        self.rate_limit_retries = rate_limit_retries
        self.rate_limit_wait = rate_limit_wait
        self.min_text_chars = min_text_chars

    def _completion(self) -> Completion:
        if self._acompletion is None:
            from litellm import acompletion

            self._acompletion = acompletion
        return self._acompletion

    async def label(self, doc: Any, types: Sequence[str]) -> dict[int, Label]:
        has_text = [len(_page_text(page).replace(" ", "")) >= self.min_text_chars for page in doc]
        if not all(has_text) and not any(m["vision"] for m in self.models):
            raise Abstain("no_vision")
        chunks: list[list[int]] = []
        for i, text in enumerate(has_text):
            batch = chunks[-1] if chunks else []
            if text and batch and has_text[batch[0]] and len(batch) < self.text_pages_per_call:
                chunks[-1].append(i)
            else:
                chunks.append([i])
        limit = asyncio.Semaphore(self.concurrency)

        async def run(chunk: list[int]) -> dict[int, Label]:
            parts = [p for i in chunk for p in self._page_part(doc[i], i + 1, has_text[i])]
            async with limit:
                return await self._label_chunk(parts, [i + 1 for i in chunk], types,
                                               images=not has_text[chunk[0]])

        labels: dict[int, Label] = {}
        for chunk_labels in await asyncio.gather(*(run(c) for c in chunks)):
            labels.update(chunk_labels)
        return labels

    def _page_part(self, page: Any, number: int, has_text: bool) -> list[dict[str, Any]]:
        import pymupdf

        if has_text:
            text = _page_text(page)
            if len(text) > 1800:
                text = f"{text[:1500]} … {text[-300:]}"
            return [{"type": "text", "text": f"--- PAGE {number} ---\n{text}"}]
        pix = page.get_pixmap(dpi=self.image_dpi, colorspace=pymupdf.csGRAY)
        url = "data:image/jpeg;base64," + base64.b64encode(pix.tobytes("jpeg")).decode()
        return [
            {"type": "text", "text": f"--- PAGE {number} --- (image)"},
            {"type": "image_url", "image_url": {"url": url}},
        ]

    async def _label_chunk(self, parts: list[dict[str, Any]], numbers: list[int],
                           types: Sequence[str], images: bool) -> dict[int, Label]:
        instruction = (
            f"Document types: {json.dumps(list(types), ensure_ascii=False)}. Use \"{OTHER}\" "
            f"for a page of any other document. Pages {numbers[0]}-{numbers[-1]} follow. Return "
            '{"pages": [{"page": <number>, "title": "<title>", "printed_page": <number|null>, '
            '"type": "<type>", "new": <true|false>}, ...]} '
            "with one entry per page."
        )
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": [{"type": "text", "text": instruction}, *parts]},
        ]
        last: Exception | None = None
        for entry in self.models:
            if images and not entry["vision"]:
                continue
            kwargs = {k: v for k, v in entry.items() if k != "vision"}
            for attempt in range(self.rate_limit_retries + 1):
                try:
                    response = await asyncio.wait_for(
                        self._completion()(
                            messages=messages,
                            temperature=0,
                            # Thinking models count thinking against max_tokens: 60/page
                            # truncated a 15-page answer. Unused budget is free.
                            max_tokens=200 * len(numbers) + 2000,
                            timeout=self.timeout,
                            **kwargs,
                        ),
                        timeout=self.timeout,
                    )
                    content = response.choices[0].message.content or ""
                    labels: dict[int, Label] = {}
                    for item in _parse_json(content).get("pages") or []:
                        try:
                            labels[int(item["page"])] = item
                        except (KeyError, TypeError, ValueError):
                            continue
                    return labels
                except Exception as exc:  # noqa: BLE001 (any provider error moves on)
                    last = exc
                    if attempt < self.rate_limit_retries and _is_rate_limit(exc):
                        await asyncio.sleep(self.rate_limit_wait * (attempt + 1))
                        continue
                    logger.warning("split: %s failed on pages %s: %s",
                                   entry["model"], numbers, str(exc)[:200])
                    break
        raise last or RuntimeError("no model in the chain can read these pages")


PageClassifier = TextPageClassifier | LLMPageClassifier


# --------------------------------------------------------------------------- entry point


def _single(page_count: int, method: str, error: str | None = None) -> SplitResult:
    n = max(page_count, 1)
    return SplitResult(n, [SplitDocument(None, 1, n)], method, error)


async def split_document(
    file_path: str,
    document_types: Sequence[str],
    classifiers: Sequence[Any],
    *,
    max_pages: int = MAX_SPLIT_PAGES,
) -> SplitResult:
    """Split the PDF at *file_path* into documents of *document_types*.

    *classifiers* run in order; the first that labels the pages wins. A classifier is any
    object with ``name`` and ``async label(doc, types) -> {page: label}`` that raises
    ``Abstain`` to pass. Failures never raise: the file comes back as one untyped document.
    """
    import pymupdf

    types = [t for t in dict.fromkeys(str(t).strip() for t in document_types or []) if t]
    try:
        doc = pymupdf.open(file_path)
    except Exception:  # noqa: BLE001 (unreadable files are read whole)
        return _single(1, "single")
    with doc:
        page_count = doc.page_count
        if not doc.is_pdf or page_count <= 1 or not types:
            return _single(page_count, "single")
        if page_count > max_pages:
            return _single(page_count, "too_long")
        reasons: list[str] = []
        error: str | None = None
        for classifier in classifiers:
            try:
                labels = await classifier.label(doc, types)
            except Abstain as why:
                reasons.append(str(why))
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("split: %s failed for %s: %s", classifier.name, file_path, exc)
                error = str(exc)[:300]
                continue
            documents = group_pages(labels, page_count, types)
            logger.info("split %s by %s: %s", file_path, classifier.name,
                        [(d.type, d.pages) for d in documents])
            return SplitResult(page_count, documents, classifier.name)
    if error:
        return _single(page_count, "fallback", error)
    return _single(page_count, reasons[-1] if reasons else "fallback")

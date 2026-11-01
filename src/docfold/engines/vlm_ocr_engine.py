"""Generic OCR-VLM engine over an OpenAI-compatible chat endpoint.

No extra install for images; PDFs need ``pip install docfold[pymupdf]``.

One adapter covers the open OCR VLMs that turn a whole page image into
Markdown in a single chat call: Xiaomi-OCR-0, HunyuanOCR-1.5, LightOnOCR-3,
OvisOCR2 and dots.ocr.  Serve the model with vLLM or SGLang (see each model
card for the exact flags), then point docfold at it::

    vllm serve lightonai/LightOnOCR-3-1B --limit-mm-per-prompt '{"image": 1}'
    export DOCFOLD_LIGHTON_OCR_URL=http://localhost:8000/v1

Each preset registers as its own engine (``--engine minicpm_ocr``) and is
available only when its ``DOCFOLD_<PRESET>_URL`` is set.  ``model`` and
``prompt`` can be overridden, so any other OpenAI-compatible VLM works too.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

_SUPPORTED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}
_MIME = {"jpg": "jpeg", "tif": "tiff"}


@dataclass(frozen=True)
class VLMPreset:
    model: str
    """Default served model id (the Hugging Face repo id)."""
    prompt: str
    """User prompt sent after the page image ("" = image only)."""
    url: str
    """Model card, for humans."""
    system: str | None = None
    """System message, when the model card sends one."""
    params: dict[str, Any] = field(default_factory=dict)
    """Extra request fields (sampling, ``chat_template_kwargs``...)."""
    postprocess: Callable[[str], str] | None = None
    """Turns the raw reply into Markdown."""


_NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}

_DOTS_PROMPT = """Please output the layout information from the PDF image, including each layout element's bbox, its category, and the corresponding text content within the bbox.

1. Bbox format: [x1, y1, x2, y2]

2. Layout Categories: The possible categories are ['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title'].

3. Text Extraction & Formatting Rules:
    - Picture: For the 'Picture' category, the text field should be omitted.
    - Formula: Format its text as LaTeX.
    - Table: Format its text as HTML.
    - All Others (Text, Title, etc.): Format their text as Markdown.

4. Constraints:
    - The output text must be the original text from the image, with no translation.
    - All layout elements must be sorted according to human reading order.

5. Final Output: The entire output must be a single JSON object.
"""  # noqa: E501 (verbatim upstream prompt)

_OTSL_TAG = re.compile(r"<(fcel|ecel|lcel|ucel|xcel|nl)>")


def _otsl_to_html(otsl: str) -> str:
    """Convert an OTSL table (Xiaomi-OCR's table syntax) to an HTML table."""
    rows: list[list[tuple[str, str]]] = [[]]
    parts = _OTSL_TAG.split(otsl)  # [text, tag, text, tag, text, ...]
    for i in range(1, len(parts), 2):
        if parts[i] == "nl":
            rows.append([])
        else:
            rows[-1].append((parts[i], parts[i + 1].strip()))
    rows = [r for r in rows if r]
    width = max((len(r) for r in rows), default=0)
    for r in rows:
        r.extend([("ecel", "")] * (width - len(r)))
    out = []
    for y, row in enumerate(rows):
        cells = []
        for x, (tag, text) in enumerate(row):
            if tag not in ("fcel", "ecel"):
                continue  # merged into a cell to the left / above
            colspan = 1
            while x + colspan < width and row[x + colspan][0] in ("lcel", "xcel"):
                colspan += 1
            rowspan = 1
            while y + rowspan < len(rows) and rows[y + rowspan][x][0] in ("ucel", "xcel"):
                rowspan += 1
            attrs = (f' rowspan="{rowspan}"' if rowspan > 1 else "") + (
                f' colspan="{colspan}"' if colspan > 1 else "")
            cells.append(f"<td{attrs}>{html.escape(text)}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(out) + "</table>"


def _otsl_tables(markdown: str) -> str:
    """Replace every paragraph written in OTSL with an HTML table."""
    blocks = re.split(r"(\n\s*\n)", markdown)
    return "".join(_otsl_to_html(b) if _OTSL_TAG.search(b) else b for b in blocks)


def _dots_to_markdown(reply: str) -> str:
    """Flatten dots.ocr layout JSON to Markdown; keep the reply if it is not JSON."""
    try:
        cells = json.loads(reply)
    except ValueError:
        return reply
    if isinstance(cells, dict):
        cells = [cells]
    out = []
    for cell in cells:
        category, text = cell.get("category"), (cell.get("text") or "").strip()
        if category in ("Page-header", "Page-footer", "Picture") or not text:
            continue
        if category == "Formula" and not text.startswith("$"):
            text = f"$$\n{text}\n$$"
        out.append(text)
    return "\n\n".join(out)


# Prompts and sampling are copied from each model card / official client.
PRESETS: dict[str, VLMPreset] = {
    "xiaomi_ocr": VLMPreset(
        model="xiaomi-research/Xiaomi-OCR-0",
        prompt=(
            "Extract all information from the main body of the document image and "
            "represent it in markdown format, ignoring headers and footers. Tables should "
            "be expressed in OTSL format, formulas in the document should be represented "
            "using LATEX format, and the parsing should be organized according to the "
            "reading order."
        ),
        url="https://huggingface.co/xiaomi-research/Xiaomi-OCR-0",
        params={"temperature": 0, "top_p": 0.8, "max_tokens": 16384, **_NO_THINKING},
        postprocess=_otsl_tables,
    ),
    "hunyuan_ocr": VLMPreset(
        model="tencent/HunyuanOCR",
        prompt=(
            "提取文档图片中正文的所有信息用markdown格式表示，其中页眉、页脚部分忽略，"
            "表格用html格式表达，文档中公式用latex格式表示，按照阅读顺序组织进行解析。"
        ),
        url="https://huggingface.co/tencent/HunyuanOCR",
        system="",
        params={
            "temperature": 0, "top_p": 1, "top_k": -1,
            "repetition_penalty": 1.08, "max_tokens": 16384,
        },
    ),
    "lighton_ocr": VLMPreset(
        model="lightonai/LightOnOCR-3-1B",
        prompt="",
        url="https://huggingface.co/lightonai/LightOnOCR-3-1B",
        params={"temperature": 0.2, "top_p": 0.9, "max_tokens": 4096},
    ),
    "ovis_ocr2": VLMPreset(
        model="ATH-MaaS/OvisOCR2",
        prompt=(
            "\nExtract all readable content from the image in natural human reading order "
            "and output the result as a single Markdown document. For charts or images, "
            "represent them using an HTML image tag: <img src=\"images/bbox_{left}_{top}_"
            "{right}_{bottom}.jpg\" />, where left, top, right, bottom are bounding box "
            "coordinates scaled to [0, 1000). Format formulas as LaTeX. Format tables as "
            "HTML: <table>...</table>. Transcribe all other text as standard Markdown. "
            "Preserve the original text without translation or paraphrasing."
        ),
        url="https://huggingface.co/ATH-MaaS/OvisOCR2",
        params={"temperature": 0, "max_tokens": 16384, **_NO_THINKING},
    ),
    "dots_ocr": VLMPreset(
        model="dots-studio/dots.ocr",
        # vLLM inserts a newline before the text unless the image tokens lead it.
        prompt="<|img|><|imgpad|><|endofimg|>" + _DOTS_PROMPT,
        url="https://huggingface.co/dots-studio/dots.ocr",
        params={"temperature": 0.1, "top_p": 0.9, "max_tokens": 32768},
        postprocess=_dots_to_markdown,
    ),
}


class VLMOCREngine(DocumentEngine):
    """Page image -> ``/chat/completions`` -> Markdown, one request per page."""

    def __init__(
        self,
        preset: str,
        base_url: str | None = None,
        model: str | None = None,
        prompt: str | None = None,
        api_key: str | None = None,
        max_tokens: int | None = None,
        dpi: int = 200,
        timeout: float = 600,
    ) -> None:
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset '{preset}'. Choose one of: {sorted(PRESETS)}")
        p = self._spec = PRESETS[preset]
        env = preset.upper()
        self._preset = preset
        self._base_url = (base_url or os.getenv(f"DOCFOLD_{env}_URL") or "").rstrip("/")
        self._model = model or os.getenv(f"DOCFOLD_{env}_MODEL") or p.model
        self._prompt = p.prompt if prompt is None else prompt
        self._api_key = api_key or os.getenv(f"DOCFOLD_{env}_API_KEY")
        self._max_tokens = max_tokens
        self._dpi = dpi
        self._timeout = timeout

    @property
    def name(self) -> str:
        return self._preset

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(table_structure=True, heading_detection=True, reading_order=True)

    def is_available(self) -> bool:
        return bool(self._base_url)

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        start = time.perf_counter()
        pages = await asyncio.get_running_loop().run_in_executor(None, self._do_process, file_path)
        return EngineResult(
            content=_format_output(pages, output_format),
            format=output_format,
            engine_name=self.name,
            pages=len(pages),
            processing_time_ms=int((time.perf_counter() - start) * 1000),
            metadata={"model": self._model, "base_url": self._base_url},
        )

    # ponytail: pages go out sequentially; fan out with a thread pool if a
    # server with batching makes that worth it.
    def _do_process(self, file_path: str) -> list[str]:
        return [self._ocr_page(img, mime) for img, mime in _page_images(file_path, self._dpi)]

    def _ocr_page(self, image: bytes, mime: str) -> str:
        parts: list[dict[str, Any]] = [{
            "type": "image_url",
            "image_url": {"url": f"data:image/{mime};base64,{base64.b64encode(image).decode()}"},
        }]
        if self._prompt:
            parts.append({"type": "text", "text": self._prompt})
        messages: list[dict[str, Any]] = []
        if self._spec.system is not None:
            messages.append({"role": "system", "content": self._spec.system})
        messages.append({"role": "user", "content": parts})
        payload: dict[str, Any] = {"model": self._model, "messages": messages, "temperature": 0}
        payload.update(self._spec.params)
        if self._max_tokens:
            payload["max_tokens"] = self._max_tokens
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        data = self._post(f"{self._base_url}/chat/completions", payload, headers)
        text = _strip_fence(data["choices"][0]["message"]["content"] or "")
        return self._spec.postprocess(text) if self._spec.postprocess else text

    def _post(self, url: str, payload: dict, headers: dict) -> dict:
        req = urllib.request.Request(url, json.dumps(payload).encode(), headers)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())


def _page_images(file_path: str, dpi: int) -> list[tuple[bytes, str]]:
    ext = Path(file_path).suffix.lstrip(".").lower()
    if ext != "pdf":
        return [(Path(file_path).read_bytes(), _MIME.get(ext, ext))]
    import fitz  # PyMuPDF

    with fitz.open(file_path) as doc:
        return [(page.get_pixmap(dpi=dpi).tobytes("png"), "png") for page in doc]


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text[:-3]
    return text.strip()


def _format_output(pages: list[str], output_format: OutputFormat) -> str:
    if output_format == OutputFormat.JSON:
        return json.dumps(
            {"pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages)]},
            ensure_ascii=False,
        )
    if output_format == OutputFormat.HTML:
        body = "\n".join(
            f"<div class='page' data-page='{i + 1}'>{t}</div>" for i, t in enumerate(pages)
        )
        return f"<html><body>{body}</body></html>"
    return "\n\n".join(pages)

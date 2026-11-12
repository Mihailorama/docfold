"""LLM checks of extracted text: internal consistency and comparison with the source pages.

Both checks go through the caller's async LLM gateway (``acompletion``, default
``litellm.acompletion``) with an ordered model fallback chain.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

Completion = Callable[..., Awaitable[Any]]

_ISSUE_SCHEMA = (
    'Return JSON only: {"issues": [{"type": "<kind>", "severity": "critical|major|minor", '
    '"description": "...", "location": "...", "expected_value": "...", "actual_value": "..."}]}. '
    'Return {"issues": []} when there are none. Report only real problems; do not guess.'
)

CONSISTENCY_PROMPT = (
    "You check extracted document text for internal consistency.\n"
    "Document context: {context}\n\nEXTRACTED TEXT:\n{text}\n\n"
    "Look for: stated row or item counts that differ from the rows listed; totals, subtotals "
    "and sums that do not add up; inconsistent date, number or currency formats; broken "
    "references or IDs; illogical values (dates out of order, impossible quantities). "
    "Kinds: row_count_mismatch, calculation_error, format_inconsistency, reference_error, "
    "logic_error. " + _ISSUE_SCHEMA
)

VISUAL_PROMPT = (
    "Compare the page images of the original document with the text extracted from it.\n"
    "Document context: {context}\n\nEXTRACTED TEXT:\n{text}\n\n"
    "Report content that is on the pages but missing from the text, values that differ "
    "(numbers, names, dates), and table structure that was broken. "
    "Kinds: missing_content, incorrect_data, table_structure, other. " + _ISSUE_SCHEMA
)


@dataclass
class ValidationResult:
    """Outcome of :func:`validate_extraction`.

    ``is_valid``: ``False`` when any critical/major issue was found, ``True``
    when the checks that ran found none, ``None`` when no check ran.
    Each issue is a dict with ``type``, ``severity``, ``description``,
    ``location``, ``expected_value``, ``actual_value`` and ``source``
    (``consistency`` or ``visual``).
    """

    is_valid: bool | None
    issues: list[dict[str, Any]] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    model: str | None = None


async def validate_extraction(
    text: str,
    models: Sequence[str | dict[str, Any]],
    *,
    file_path: str | None = None,
    acompletion: Completion | None = None,
    context: str = "General document",
    visual: bool = True,
    max_pages: int = 3,
    dpi: int = 110,
    max_text_chars: int = 60_000,
) -> ValidationResult:
    """Check *text* (extracted from *file_path*) with an LLM.

    1. Consistency: text only (counts, totals, formats, references).
    2. Visual (when *visual*, *file_path* is given and it has at most
       *max_pages* pages): page images vs the text; needs PyMuPDF.

    A failing model moves to the next one in *models*; a check whose models
    all fail, or whose answer is not JSON, is listed in ``skipped``.
    """
    if not models:
        raise ValueError("validate_extraction needs at least one model")
    if acompletion is None:
        from litellm import acompletion as _litellm

        acompletion = _litellm
    sample = text[:max_text_chars]
    result = ValidationResult(is_valid=None)

    async def run(name: str, content: Any) -> None:
        messages = [{"role": "user", "content": content}]
        last = "no model answered"
        for entry in models:
            kwargs = {"model": entry} if isinstance(entry, str) else dict(entry)
            try:
                response = await acompletion(messages=messages, temperature=0, **kwargs)
                issues = _parse_issues(response.choices[0].message.content or "")
            except Exception as exc:  # noqa: BLE001 - any provider/parse error moves on
                last = str(exc)[:200]
                logger.warning("validate %s: %s failed: %s", name, kwargs.get("model"), last)
                continue
            result.issues += [{**i, "source": name} for i in issues]
            result.checks.append(name)
            result.model = kwargs.get("model")
            return
        result.skipped[name] = last

    await run("consistency", _fill(CONSISTENCY_PROMPT, context, sample))

    if visual and file_path:
        pages = _page_images(file_path, max_pages, dpi)
        if isinstance(pages, str):
            result.skipped["visual"] = pages
        else:
            parts: list[dict[str, Any]] = [
                {"type": "text", "text": _fill(VISUAL_PROMPT, context, sample)}
            ]
            parts += [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                for b64 in pages
            ]
            await run("visual", parts)

    if result.checks:
        result.is_valid = not any(
            i.get("severity") in ("critical", "major") for i in result.issues
        )
    return result


def _page_images(file_path: str, max_pages: int, dpi: int) -> list[str] | str:
    """Base64 JPEG pages, or the reason the visual check is skipped."""
    try:
        import pymupdf

        from docfold.render import render_pages

        with pymupdf.open(file_path) as doc:
            count = doc.page_count
    except Exception as exc:  # noqa: BLE001
        return f"cannot render pages: {exc}"
    if count > max_pages:
        return f"document has {count} pages (limit {max_pages})"
    return [
        base64.b64encode(data).decode()
        for _, data in render_pages(file_path, dpi=dpi, image_format="jpeg", quality=80)
    ]


def _fill(prompt: str, context: str, text: str) -> str:
    return prompt.replace("{context}", context).replace("{text}", text)


def _parse_issues(answer: str) -> list[dict[str, Any]]:
    match = re.search(r"\{.*\}", answer, re.S)
    if not match:
        raise ValueError("no JSON in the answer")
    issues = json.loads(match.group(0)).get("issues") or []
    keys = ("type", "severity", "description", "location", "expected_value", "actual_value")
    return [{k: i.get(k) for k in keys} for i in issues if isinstance(i, dict)]

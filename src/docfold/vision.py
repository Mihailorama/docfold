"""Vision LLM captions for images extracted from documents.

Logos, stamps, charts and scanned tables carry text that layout engines skip.
``caption_images`` describes them in one batched call through the caller's own
LLM gateway (``acompletion``), with an ordered model fallback chain.

Install ``docfold[split-llm]`` (LiteLLM) unless you pass your own ``acompletion``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

Completion = Callable[..., Awaitable[Any]]

DEFAULT_PROMPT = (
    "Analyze the provided image(s) from a document. Respond in the language of the "
    "document text sample: <TEXT_SAMPLE>{sample}</TEXT_SAMPLE>. For each image, extract "
    "its text and important information and describe its content; return tables as "
    "structured tables with all values. Return only the analysis, no advice or questions. "
    "If an image has no meaningful content, return an empty string for it. "
    "If there are several images, analyze each one separately and prefix each analysis "
    "with the image filename in brackets, e.g. [image_name.png]: analysis."
)

_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
         "gif": "image/gif", "webp": "image/webp"}


async def caption_images(
    images: dict[str, str] | None,
    models: Sequence[str | dict[str, Any]],
    *,
    acompletion: Completion | None = None,
    document_text: str = "",
    min_image_bytes: int = 5_000,
    prompt: str | None = None,
    max_tokens: int = 10_000,
) -> dict[str, str]:
    """Describe document images with a vision model in one call.

    Args:
        images: ``{filename: base64}``, e.g. ``EngineResult.images``.
        models: Ordered fallback chain: LiteLLM model names or kwargs dicts
            (``{"model": "...", "api_key": "..."}``); a failing call moves on.
        acompletion: Async LLM caller; defaults to ``litellm.acompletion``.
        document_text: Sample used to answer in the document's language.
        min_image_bytes: Smaller images (icons, bullets) are skipped.
        prompt: Instruction override; ``{sample}`` is filled with the text sample.

    Returns:
        ``{filename: analysis}`` for the eligible images; ``""`` for each when
        every model fails. ``{}`` when no image is eligible.
    """
    if not models:
        raise ValueError("caption_images needs at least one model")
    eligible = {n: b for n, b in (images or {}).items() if len(b) * 3 // 4 >= min_image_bytes}
    if not eligible:
        return {}
    if acompletion is None:
        from litellm import acompletion as _litellm

        acompletion = _litellm
    text = (prompt or DEFAULT_PROMPT).replace("{sample}", (document_text or "")[:300])
    parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for name, b64 in eligible.items():
        mime = _MIME.get(name.rsplit(".", 1)[-1].lower(), "image/jpeg")
        # Name each image in the request; without it models invent [image_1] labels.
        parts.append({"type": "text", "text": f"[{name}]"})
        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
    messages = [{"role": "user", "content": parts}]
    names = list(eligible)
    for entry in models:
        kwargs = {"model": entry} if isinstance(entry, str) else dict(entry)
        try:
            response = await acompletion(messages=messages, max_tokens=max_tokens, **kwargs)
            raw = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - any provider error moves on
            logger.warning("caption_images: %s failed: %s", kwargs.get("model"), str(exc)[:200])
            continue
        return split_answer(raw, names)
    return {name: "" for name in names}


def split_answer(raw: str, names: list[str]) -> dict[str, str]:
    """Split a batched answer by ``[name]`` markers.

    One image takes the whole answer; when no marker is found every image gets
    the whole answer; images without a marker get ``""``.
    """
    if not raw:
        return {n: "" for n in names}
    if len(names) == 1:
        return {names[0]: raw}
    found = sorted((raw.find(f"[{n}]"), n) for n in names if f"[{n}]" in raw)
    if not found:
        return {n: raw for n in names}
    out = {n: "" for n in names}
    for i, (pos, name) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(raw)
        out[name] = raw[pos + len(name) + 2:end].strip().lstrip(":").strip()
    return out


CORRECTION_PROMPT = (
    "The text below was produced by OCR and may contain recognition errors. Fix OCR "
    "errors only (misread characters, broken words, wrong line joins); keep the wording, "
    "numbers that are clearly legible, order and Markdown structure. Do not translate, "
    "summarize or add content.{image_hint}\nContext: {context}\n\nOCR TEXT:\n{text}\n\n"
    "Return only the corrected text."
)


async def correct_ocr_text(
    text: str,
    models: Sequence[str | dict[str, Any]],
    *,
    acompletion: Completion | None = None,
    image_b64: str | None = None,
    image_mime: str = "image/jpeg",
    context: str = "",
    max_tokens: int = 16_000,
) -> str:
    """Fix OCR errors in *text* with an LLM; returns *text* unchanged when every model fails.

    Pass the page image (*image_b64*) so the model can check unclear characters.
    *models* is an ordered fallback chain; *acompletion* defaults to
    ``litellm.acompletion``.
    """
    if not models:
        raise ValueError("correct_ocr_text needs at least one model")
    if not text.strip():
        return text
    if acompletion is None:
        from litellm import acompletion as _litellm

        acompletion = _litellm
    hint = " The page image is attached; use it to resolve unclear characters." if image_b64 else ""
    prompt = (CORRECTION_PROMPT.replace("{image_hint}", hint)
              .replace("{context}", context or "none").replace("{text}", text))
    content: Any = prompt
    if image_b64:
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url",
                    "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}}]
    for entry in models:
        kwargs = {"model": entry} if isinstance(entry, str) else dict(entry)
        try:
            response = await acompletion(messages=[{"role": "user", "content": content}],
                                         temperature=0, max_tokens=max_tokens, **kwargs)
            fixed = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - any provider error moves on
            logger.warning("correct_ocr_text: %s failed: %s", kwargs.get("model"), str(exc)[:200])
            continue
        if fixed:
            return fixed
    return text

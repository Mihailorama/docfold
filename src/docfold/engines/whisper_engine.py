"""Whisper audio transcription through an injectable caller.

``atranscription`` defaults to ``litellm.atranscription`` (``pip install
litellm``); pass your own gateway to keep model management and cost logging.
OpenAI limits uploads to 25 MB.
"""

from __future__ import annotations

import html
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from docfold.engines.base import DocumentEngine, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_EXTENSIONS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac"}


class WhisperEngine(DocumentEngine):
    """Audio -> text with Whisper (``whisper-1`` by default).

    Args:
        models: Ordered fallback chain: model names or kwargs dicts
            (``{"model": "groq/whisper-large-v3", "api_key": "..."}``).
        atranscription: Async caller ``(model=, file=, **kwargs)`` returning an
            object or dict with ``text``.
    """

    def __init__(
        self,
        models: Sequence[str | dict[str, Any]] = ("whisper-1",),
        atranscription: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self._models = [{"model": m} if isinstance(m, str) else dict(m) for m in models]
        self._atranscription = atranscription

    @property
    def name(self) -> str:
        return "whisper"

    @property
    def supported_extensions(self) -> set[str]:
        return _EXTENSIONS

    def is_available(self) -> bool:
        if self._atranscription is not None:
            return True
        try:
            import litellm  # noqa: F401
        except ImportError:
            return False
        return bool(os.getenv("OPENAI_API_KEY"))

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()
        call = self._atranscription
        if call is None:
            from litellm import atranscription

            call = atranscription
        last: Exception | None = None
        for entry in self._models:
            try:
                with open(file_path, "rb") as fh:
                    response = await call(file=fh, **entry)
            except Exception as exc:  # noqa: BLE001 - any provider error moves on
                logger.warning("whisper: %s failed: %s", entry.get("model"), str(exc)[:200])
                last = exc
                continue
            text = response.get("text", "") if isinstance(response, dict) else response.text
            text = (text or "").strip()
            if output_format == OutputFormat.JSON:
                content = json.dumps({"text": text}, ensure_ascii=False)
            elif output_format == OutputFormat.HTML:
                content = f"<p>{html.escape(text)}</p>"
            else:
                content = text
            return EngineResult(
                content=content,
                format=output_format,
                engine_name=self.name,
                processing_time_ms=int((time.perf_counter() - start) * 1000),
                metadata={"model": entry.get("model")},
            )
        raise RuntimeError(f"All Whisper models failed: {last}")

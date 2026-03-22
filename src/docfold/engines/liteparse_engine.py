"""LiteParse engine adapter — fast local document parsing via CLI.

LiteParse is a standalone OSS tool by LlamaIndex for high-speed PDF parsing
with bounding boxes.  It runs locally with no API key required.

Requires Node.js 18+ and the ``lit`` CLI:
``npm i -g @llamaindex/liteparse``

See https://github.com/run-llama/liteparse
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from typing import Any

from docfold.engines.base import (
    BoundingBox,
    DocumentEngine,
    EngineCapabilities,
    EngineResult,
    OutputFormat,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls",
    "odt", "rtf", "odp", "csv", "tsv",
    "png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp",
}


class LiteParseEngine(DocumentEngine):
    """Adapter for LiteParse (run-llama/liteparse).

    Calls the ``lit parse`` CLI as a subprocess and parses the structured
    JSON output.  Supports bounding boxes and confidence scores out of the box.
    """

    def __init__(
        self,
        cli_path: str = "lit",
        ocr_enabled: bool = True,
        ocr_language: str = "en",
        dpi: int = 150,
        num_workers: int | None = None,
        max_pages: int | None = None,
    ) -> None:
        self._cli_path = cli_path
        self._ocr_enabled = ocr_enabled
        self._ocr_language = ocr_language
        self._dpi = dpi
        self._num_workers = num_workers
        self._max_pages = max_pages

    @property
    def name(self) -> str:
        return "liteparse"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(bounding_boxes=True, confidence=True)

    def is_available(self) -> bool:
        return shutil.which(self._cli_path) is not None

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        start = time.perf_counter()

        # For text output we use --format text; for everything else use json
        # so we can extract bounding boxes.
        use_json = output_format != OutputFormat.TEXT

        cmd = self._build_command(file_path, use_json=use_json)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            raise RuntimeError(
                f"liteparse failed (exit {proc.returncode}): {err_msg}"
            )

        raw = stdout.decode(errors="replace")
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if use_json:
            return self._parse_json_output(raw, output_format, elapsed_ms)
        else:
            return EngineResult(
                content=raw,
                format=output_format,
                engine_name=self.name,
                processing_time_ms=elapsed_ms,
                metadata={"cli": self._cli_path},
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_command(self, file_path: str, *, use_json: bool) -> list[str]:
        cmd = [self._cli_path, "parse", file_path]

        if use_json:
            cmd += ["--format", "json"]
        else:
            cmd += ["--format", "text"]

        if not self._ocr_enabled:
            cmd.append("--no-ocr")
        else:
            cmd += ["--ocr-language", self._ocr_language]

        if self._dpi != 150:
            cmd += ["--dpi", str(self._dpi)]

        if self._num_workers is not None:
            cmd += ["--num-workers", str(self._num_workers)]

        if self._max_pages is not None:
            cmd += ["--max-pages", str(self._max_pages)]

        return cmd

    def _parse_json_output(
        self,
        raw: str,
        output_format: OutputFormat,
        elapsed_ms: int,
    ) -> EngineResult:
        data = json.loads(raw)
        pages = data.get("pages", [])

        texts: list[str] = []
        bboxes: list[dict[str, Any]] = []

        for page_data in pages:
            page_num = page_data.get("page", 1)
            content_block = page_data.get("content", {})
            page_text = content_block.get("text", "")
            texts.append(page_text)

            pw = page_data.get("width")
            ph = page_data.get("height")

            for idx, item in enumerate(content_block.get("items", [])):
                bboxes.append(
                    BoundingBox(
                        type="Text",
                        bbox=item.get("bbox", []),
                        page=page_num,
                        text=item.get("text", ""),
                        id=f"p{page_num}-i{idx}",
                        confidence=item.get("confidence"),
                        page_width=pw,
                        page_height=ph,
                    ).to_dict()
                )

        full_text = "\n\n".join(texts)
        page_count = len(pages)

        if output_format == OutputFormat.JSON:
            content = json.dumps(data, ensure_ascii=False)
        elif output_format == OutputFormat.HTML:
            html_parts = [
                f"<div class='page' data-page='{i + 1}'><p>{t}</p></div>"
                for i, t in enumerate(texts)
            ]
            content = "<html><body>" + "\n".join(html_parts) + "</body></html>"
        else:
            # MARKDOWN or TEXT — return extracted text
            content = full_text

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=page_count,
            processing_time_ms=elapsed_ms,
            bounding_boxes=bboxes or None,
            metadata={"cli": self._cli_path, "page_count": page_count},
        )

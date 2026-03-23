"""Marker API (Datalab) engine adapter.

Install: ``pip install docfold[marker]``

Requires a Datalab API key: https://www.datalab.to/

All current Marker API parameters (as of 2026-02) are supported:

- At **construction time** — set defaults for every call::

      engine = MarkerEngine(mode="balanced", paginate=True)

- At **call time** via ``**kwargs`` — override per request::

      result = await router.process("doc.pdf", mode="fast", max_pages=5)

See https://documentation.datalab.to/ for parameter docs.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
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
    "odt", "odp", "ods", "html", "epub",
    "png", "jpg", "jpeg", "webp", "gif", "tiff",
}

_API_BASE = "https://www.datalab.to/api/v1/marker"
_DEFAULT_POLL_INTERVAL = 2
_DEFAULT_MAX_POLLS = 300

# Valid Marker API parameters (non-deprecated, as of 2026-02).
# Used to filter kwargs before sending to the API.
_VALID_MARKER_PARAMS = {
    "mode",                     # fast | balanced | accurate
    "use_llm",                  # bool — LLM for tables, forms, math, image captions
    "force_ocr",                # bool — force OCR even on text-based PDFs
    "block_correction_prompt",  # str — optional LLM correction prompt
    "paginate",                 # bool — add page delimiters
    "max_pages",                # int — limit pages processed
    "page_range",               # str — e.g. "0,2-4" (0-indexed)
    "page_schema",              # str — JSON schema for structured extraction
    "segmentation_schema",      # str — schema for auto-segmentation
    "disable_image_extraction", # bool — if use_llm=True, images replaced with captions
    "disable_image_captions",   # bool
    "disable_ocr_math",        # bool — disable inline math recognition
    "add_block_ids",            # bool
    "skip_cache",               # bool
    "save_checkpoint",          # bool
    "additional_config",        # str — JSON string
    "extras",                   # str — JSON string
    "webhook_url",              # str
}


class MarkerEngine(DocumentEngine):
    """Adapter for the Marker API (Datalab SaaS).

    Constructor kwargs set defaults for every ``process()`` call.
    Per-call ``**kwargs`` in ``process()`` override constructor defaults.

    Example::

        engine = MarkerEngine(mode="accurate", paginate=True)
        # This call uses mode="accurate", paginate=True (from constructor)
        result = await engine.process("doc.pdf", output_format=OutputFormat.HTML)

        # This call overrides mode to "fast" for this request only
        result = await engine.process("doc.pdf", mode="fast")

    See https://documentation.datalab.to/
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        mode: str = "accurate",
        paginate: bool = False,
        disable_image_extraction: bool = False,
        **kwargs: Any,
    ) -> None:
        self._api_key = api_key or os.getenv("MARKER_API_KEY") or os.getenv("DATALAB_API_KEY")
        # Store all constructor params as defaults for every API call
        self._defaults: dict[str, Any] = {
            "mode": mode,
            "paginate": paginate,
            "disable_image_extraction": disable_image_extraction,
        }
        # Accept any additional valid Marker params as constructor defaults
        for key, value in kwargs.items():
            if key in _VALID_MARKER_PARAMS:
                self._defaults[key] = value
            else:
                logger.warning("MarkerEngine: unknown param %r ignored", key)

    @property
    def name(self) -> str:
        return "marker"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            bounding_boxes=True, confidence=True, images=True,
            table_structure=True, heading_detection=True,
        )

    def is_available(self) -> bool:
        try:
            import requests  # noqa: F401
            return bool(self._api_key)
        except ImportError:
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        """Process a document via the Marker API.

        Any ``**kwargs`` that match valid Marker API parameters override
        the constructor defaults for this call only.
        """
        import asyncio

        # Merge: constructor defaults ← per-call overrides
        merged = dict(self._defaults)
        for key, value in kwargs.items():
            if key in _VALID_MARKER_PARAMS:
                merged[key] = value
            # Silently ignore non-Marker kwargs (e.g. engine_hint from router)

        start = time.perf_counter()

        loop = asyncio.get_running_loop()
        content, images, meta, bboxes = await loop.run_in_executor(
            None, self._call_marker, file_path, output_format, merged
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Marker returns parse_quality_score (0-1) when available
        quality_score = meta.get("marker_json", {}).get("parse_quality_score")

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            images=images,
            bounding_boxes=bboxes,
            confidence=quality_score,
            pages=meta.get("page_count"),
            processing_time_ms=elapsed_ms,
            metadata=meta,
        )

    def _call_marker(
        self,
        file_path: str,
        output_format: OutputFormat,
        params: dict[str, Any],
    ) -> tuple[str, dict | None, dict, list[dict[str, Any]] | None]:
        import requests

        # Always request JSON from Marker to get bounding boxes.
        # JSON response includes bbox, polygon, block_type, and html per block.
        # We reconstruct the requested format from the JSON tree.
        fmt_map = {
            OutputFormat.MARKDOWN: "markdown",
            OutputFormat.HTML: "html",
            OutputFormat.JSON: "json",
            OutputFormat.TEXT: "markdown",
        }
        requested_fmt = fmt_map[output_format]

        headers = {"X-Api-Key": self._api_key}

        with open(file_path, "rb") as f:
            import mimetypes
            mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            form_data: dict[str, Any] = {
                "file": (Path(file_path).name, f, mime_type),
                "output_format": (None, "json"),
            }
            # Add all Marker params to the form data
            for key, value in params.items():
                if isinstance(value, bool):
                    form_data[key] = (None, str(value))
                elif value is not None:
                    form_data[key] = (None, str(value))

            resp = requests.post(_API_BASE, files=form_data, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        check_url = data["request_check_url"]

        for _ in range(_DEFAULT_MAX_POLLS):
            time.sleep(_DEFAULT_POLL_INTERVAL)
            resp = requests.get(check_url, headers=headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            if result.get("status") == "complete":
                images = result.get("images")
                json_tree = result.get("json") or {}

                # Extract bounding boxes and content from JSON tree.
                # Structure: json -> children[Page] -> children[Block...]
                # Each block has: bbox, block_type, id, polygon, html
                bboxes: list[dict[str, Any]] = []
                html_parts: list[str] = []
                md_parts: list[str] = []
                for page_idx, page_node in enumerate(
                    json_tree.get("children") or [],
                ):
                    page_num = page_idx + 1
                    # Page dimensions from the Page node bbox [0, 0, W, H]
                    page_bbox = page_node.get("bbox")
                    pw: float | None = None
                    ph: float | None = None
                    if (
                        isinstance(page_bbox, list)
                        and len(page_bbox) >= 4
                    ):
                        pw = float(page_bbox[2] - page_bbox[0])
                        ph = float(page_bbox[3] - page_bbox[1])
                    for idx, block in enumerate(
                        page_node.get("children") or [],
                    ):
                        bbox_raw = block.get("bbox")
                        if bbox_raw:
                            bboxes.append(BoundingBox(
                                type=block.get("block_type", "Text"),
                                bbox=bbox_raw,
                                page=page_num,
                                text=block.get("html", ""),
                                id=block.get("id") or f"p{page_num}-b{idx}",
                                polygon=block.get("polygon"),
                                page_width=pw,
                                page_height=ph,
                            ).to_dict())
                        block_html = block.get("html", "")
                        if block_html:
                            html_parts.append(block_html)
                        block_md = block.get("content", "")
                        if block_md:
                            md_parts.append(block_md)

                # Reconstruct content in the requested format
                if requested_fmt == "json":
                    import json as _json
                    content = _json.dumps(json_tree, ensure_ascii=False)
                elif requested_fmt == "html":
                    content = "\n".join(html_parts)
                else:
                    # markdown / text
                    content = "\n\n".join(md_parts) if md_parts else "\n".join(html_parts)

                meta = {
                    "page_count": result.get("page_count"),
                    "marker_output_format": requested_fmt,
                    "params": params,
                    "marker_json": result,
                }
                return content, images, meta, bboxes or None

            if result.get("status") == "failed":
                raise RuntimeError(f"Marker API failed: {result.get('error')}")

        raise TimeoutError("Marker API did not complete within the polling window.")

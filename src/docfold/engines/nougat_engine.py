"""Nougat engine adapter — Meta's academic document understanding model.

Install: ``pip install docfold[nougat]``

Nougat (Neural Optical Understanding for Academic Documents) is a transformer
model trained on arXiv papers.  It excels at converting academic PDFs —
including LaTeX formulas — into Markdown.

No API key needed; runs entirely locally.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from docfold.engines.base import DocumentEngine, EngineCapabilities, EngineResult, OutputFormat

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {"pdf"}


class NougatEngine(DocumentEngine):
    """Adapter for Meta Nougat (academic PDF → Markdown).

    Best for scientific papers with heavy math notation.  Produces Mathpix-
    compatible Markdown with LaTeX equations.

    See https://github.com/facebookresearch/nougat
    """

    def __init__(
        self,
        model: str = "facebook/nougat-small",
        batch_size: int = 1,
        no_skipping: bool = False,
    ) -> None:
        self._model = model
        self._batch_size = batch_size
        self._no_skipping = no_skipping

    @property
    def name(self) -> str:
        return "nougat"

    @property
    def supported_extensions(self) -> set[str]:
        return _SUPPORTED_EXTENSIONS

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            table_structure=True,
            heading_detection=True,
            reading_order=True,
        )

    def is_available(self) -> bool:
        try:
            import nougat  # noqa: F401
            return True
        except Exception:
            return False

    async def process(
        self,
        file_path: str,
        output_format: OutputFormat = OutputFormat.MARKDOWN,
        **kwargs: Any,
    ) -> EngineResult:
        import asyncio

        start = time.perf_counter()

        loop = asyncio.get_running_loop()
        content, page_count = await loop.run_in_executor(
            None, self._do_process, file_path, output_format
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return EngineResult(
            content=content,
            format=output_format,
            engine_name=self.name,
            pages=page_count,
            processing_time_ms=elapsed_ms,
            metadata={"model": self._model},
        )

    def _do_process(
        self, file_path: str, output_format: OutputFormat
    ) -> tuple[str, int]:
        import torch
        from nougat import NougatModel
        from nougat.postprocessing import markdown_compatible
        from nougat.utils.dataset import LazyDataset
        from nougat.utils.device import move_to_device
        from torch.utils.data import DataLoader

        # NougatConfig defaults decoder_layer=10, but nougat-small only has
        # 4 decoder layers.  Read the actual value from the HF config and
        # monkey-patch NougatConfig so the model architecture matches the
        # checkpoint.
        import json as _json
        from huggingface_hub import hf_hub_download
        from nougat.model import NougatConfig

        cfg_path = hf_hub_download(self._model, "config.json")
        with open(cfg_path) as _f:
            _raw = _json.load(_f)
        actual_dec_layers = (
            _raw.get("decoder", {}).get("decoder_layers")
            or NougatConfig().decoder_layer
        )

        _orig_init = NougatConfig.__init__

        def _patched_init(self_cfg, *a, **kw):
            kw.setdefault("decoder_layer", actual_dec_layers)
            _orig_init(self_cfg, *a, **kw)

        NougatConfig.__init__ = _patched_init
        try:
            model = NougatModel.from_pretrained(
                self._model, use_safetensors=False,
            )
        finally:
            NougatConfig.__init__ = _orig_init

        # Newer transformers nests decoder keys under an extra ".model."
        # prefix.  Re-load decoder weights with the corrected key mapping.
        ckpt_path = hf_hub_download(self._model, "pytorch_model.bin")
        ckpt = torch.load(ckpt_path, map_location="cpu")

        decoder_state: dict[str, torch.Tensor] = {}
        for k, v in ckpt.items():
            if not k.startswith("decoder.model."):
                continue
            sub_key = k[len("decoder.model."):]
            decoder_state["model." + sub_key] = v
        if "model.decoder.embed_tokens.weight" in decoder_state:
            decoder_state["lm_head.weight"] = decoder_state[
                "model.decoder.embed_tokens.weight"
            ]

        # Handle embed_positions shape differences
        model_sd = model.decoder.model.state_dict()
        for k in list(decoder_state.keys()):
            if k in model_sd and decoder_state[k].shape != model_sd[k].shape:
                cs, ms = decoder_state[k].shape, model_sd[k].shape
                if len(cs) == 2 and len(ms) == 2 and cs[1] == ms[1]:
                    if cs[0] < ms[0]:
                        padded = torch.zeros(ms)
                        padded[: cs[0]] = decoder_state[k]
                        decoder_state[k] = padded
                    else:
                        decoder_state[k] = decoder_state[k][: ms[0]]
                else:
                    del decoder_state[k]

        model.decoder.model.load_state_dict(decoder_state, strict=False)

        model = move_to_device(model)
        model.eval()

        dataset = LazyDataset(
            file_path,
            model.encoder.prepare_input,
        )
        dataloader = DataLoader(
            dataset,
            batch_size=self._batch_size,
            shuffle=False,
        )

        pages_text: list[str] = []
        for idx, sample in enumerate(dataloader):
            if isinstance(sample, (list, tuple)):
                image_tensor = sample[0]
            else:
                image_tensor = sample

            if image_tensor is None:
                pages_text.append("")
                continue

            image_tensor = image_tensor.to(model.device)

            with torch.no_grad():
                output = model.inference(
                    image_tensors=image_tensor,
                    early_stopping=not self._no_skipping,
                )

            for page_text in output["predictions"]:
                page_text = markdown_compatible(page_text)
                pages_text.append(page_text)

        page_count = len(pages_text)
        full_text = "\n\n".join(pages_text)

        if output_format == OutputFormat.JSON:
            import json
            content = json.dumps(
                {"pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages_text)]},
                ensure_ascii=False,
            )
        elif output_format == OutputFormat.HTML:
            html_parts = [
                f"<div class='page' data-page='{i + 1}'><p>{t}</p></div>"
                for i, t in enumerate(pages_text)
            ]
            content = "<html><body>" + "\n".join(html_parts) + "</body></html>"
        else:
            content = full_text

        return content, page_count

"""Minimal Modal server for ``RemoteMarkerEngine`` (docfold).

Deploy:  modal deploy docs/examples/modal_marker_app.py
Then:    export MODAL_MARKER_URL=<the printed web endpoint URL>
"""

import modal

app = modal.App("docfold-marker")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install("marker-pdf>=1.6,<2", "torch>=2.4", "fastapi[standard]")
    # Bake model weights into the image so cold starts skip the download.
    .run_commands("python -c 'from marker.models import create_model_dict; create_model_dict()'")
)


@app.cls(image=image, gpu="A10G", timeout=300, scaledown_window=600, min_containers=0)
class Marker:
    @modal.enter()
    def load(self):
        from marker.models import create_model_dict

        self.models = create_model_dict()

    @modal.fastapi_endpoint(method="POST")
    def process(self, request: dict) -> dict:
        import base64
        import tempfile
        import time
        from pathlib import Path

        from marker.converters.pdf import PdfConverter
        from marker.output import text_from_rendered

        start = time.perf_counter()
        renderer = (
            "marker.renderers.html.HTMLRenderer"
            if request.get("output_format") == "html"
            else "marker.renderers.markdown.MarkdownRenderer"
        )
        suffix = Path(request.get("filename", "document.pdf")).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(base64.b64decode(request["file_base64"]))
            tmp.flush()
            rendered = PdfConverter(artifact_dict=self.models, renderer=renderer)(tmp.name)
        text, _, images = text_from_rendered(rendered)
        return {
            "content": text,
            "images": {k: _b64(v) for k, v in (images or {}).items()},
            "pages": (getattr(rendered, "metadata", None) or {}).get("page_count"),
            "processing_time_ms": int((time.perf_counter() - start) * 1000),
        }


def _b64(img) -> str:
    import base64
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

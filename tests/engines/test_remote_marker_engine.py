"""Remote (Modal) Marker engine (DOCFOLD-16)."""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.remote_marker_engine import RemoteMarkerEngine


class _Server:
    def __init__(self, fail_first=0):
        self.requests = []
        self.fail = fail_first
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                if outer.fail:
                    outer.fail -= 1
                    self.send_response(502)
                    self.end_headers()
                    return
                data = json.dumps({"content": "# Doc", "images": {"i.png": "aGk="},
                                   "pages": 2, "processing_time_ms": 900}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/"

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4 test")
    return str(p)


async def test_maps_request_and_result(pdf):
    srv = _Server()
    try:
        res = await RemoteMarkerEngine(url=srv.url).process(pdf, output_format=OutputFormat.HTML)
    finally:
        srv.close()
    body = srv.requests[0]
    assert base64.b64decode(body["file_base64"]) == b"%PDF-1.4 test"
    assert body["filename"] == "a.pdf" and body["output_format"] == "html"
    assert res.engine_name == "modal_marker" and res.content == "# Doc" and res.pages == 2
    assert res.images == {"i.png": "aGk="}
    assert res.metadata["gpu_processing_time_ms"] == 900
    assert res.metadata["wall_time_ms"] >= 0


async def test_retry(pdf):
    srv = _Server(fail_first=1)
    try:
        res = await RemoteMarkerEngine(url=srv.url, retries=1).process(pdf)
        assert res.content == "# Doc" and len(srv.requests) == 2
        srv.fail = 5
        with pytest.raises(RuntimeError, match="502"):
            await RemoteMarkerEngine(url=srv.url, retries=1).process(pdf)
    finally:
        srv.close()


def test_availability(monkeypatch):
    monkeypatch.delenv("DOCFOLD_REMOTE_MARKER_URL", raising=False)
    monkeypatch.delenv("MODAL_MARKER_URL", raising=False)
    assert not RemoteMarkerEngine().is_available()
    monkeypatch.setenv("MODAL_MARKER_URL", "https://x.modal.run")
    assert RemoteMarkerEngine().is_available()
    assert RemoteMarkerEngine(name="gpu_marker").name == "gpu_marker"

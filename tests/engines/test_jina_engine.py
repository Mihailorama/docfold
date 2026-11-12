"""Jina Reader engine (DOCFOLD-19)."""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.jina_engine import JinaEngine


@pytest.fixture
def server():
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((dict(self.headers), body))
            out = json.dumps({"code": 200, "data": {
                "title": "Doc", "content": "# Doc\n\ntext", "usage": {"tokens": 12}}}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/", seen
    httpd.shutdown()


async def test_request_and_result(server, tmp_path):
    url, seen = server
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    res = await JinaEngine(api_key="k", base_url=url).process(str(pdf))
    headers, body = seen[0]
    assert base64.b64decode(body["pdf"]) == b"%PDF-1.4 x"
    assert headers["Authorization"] == "Bearer k"
    assert headers["X-Return-Format"] == "markdown"
    assert res.content == "# Doc\n\ntext"
    assert res.metadata == {"title": "Doc", "tokens": 12}
    j = await JinaEngine(api_key="k", base_url=url).process(str(pdf), OutputFormat.JSON)
    assert json.loads(j.content) == {"title": "Doc", "content": "# Doc\n\ntext"}
    await JinaEngine(api_key="k", base_url=url).process(str(pdf), OutputFormat.HTML)
    assert seen[-1][0]["X-Return-Format"] == "html"


def test_availability(monkeypatch):
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.delenv("JINAAI_API_KEY", raising=False)
    assert not JinaEngine().is_available()
    monkeypatch.setenv("JINAAI_API_KEY", "x")
    assert JinaEngine().is_available()

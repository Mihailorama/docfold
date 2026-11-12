---
purpose: "Run Marker on your own GPU endpoint (Modal or any HTTP host)"
status: "DONE"
priority: "P2"
created: "2026-11-12"
---

# Feature: Remote Marker engine (DOCFOLD-16)

## Problem
`marker` uses the Datalab SaaS and `marker_local` needs a local GPU. Teams that
host marker-pdf on a serverless GPU (Modal, RunPod, their own box) have no
engine for it.

## Proposed Solution
`RemoteMarkerEngine(url=None, name="modal_marker", timeout=120, retries=1)`:
POSTs `{"file_base64", "filename", "output_format"}` JSON to `url` and reads
`{"content", "images", "pages", "processing_time_ms"}`. URL from the argument,
`DOCFOLD_REMOTE_MARKER_URL`, or `MODAL_MARKER_URL`. Retries timeouts and HTTP
errors `retries` times. `metadata`: `gpu_processing_time_ms`, `wall_time_ms`.
A minimal Modal server is in `docs/examples/modal_marker_app.py`.

## Test Plan
- [x] request body and result mapping against a local HTTP server
- [x] retry then success; retries exhausted -> error
- [x] availability from env

```bash
pytest tests/engines/test_remote_marker_engine.py -v
```

## Out of Scope
- Bounding boxes: the example server returns rendered text only.

---
purpose: "Audio transcription with Whisper through an injectable caller"
status: "DONE"
priority: "P2"
created: "2026-11-12"
---

# Feature: Whisper audio engine (DOCFOLD-18)

## Problem
Audio goes through markitdown, whose transcription differs from OpenAI
`whisper-1`. Callers that already use Whisper cannot keep the same output, and
cannot route the call through their own gateway.

## Proposed Solution
`WhisperEngine(models=["whisper-1"], atranscription=None)`, name `whisper`:
- calls `await atranscription(model=..., file=<binary file>, **kwargs)` and
  returns `response.text` (LiteLLM / OpenAI SDK shape, or a dict with `text`);
  `atranscription` defaults to `litellm.atranscription`.
- `models` is an ordered fallback chain (names or kwargs dicts).
- output: text for MARKDOWN/TEXT/HTML (HTML wrapped in `<p>`), `{"text": ...}` for JSON.
- available when a caller is injected, or LiteLLM is installed and
  `OPENAI_API_KEY` is set.
- extensions: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg, flac. Added after
  markitdown in the router's audio lists, so default routing is unchanged.

## Test Plan
- [x] injected caller: model, file handle, text output, JSON output
- [x] fallback chain on error; all fail -> RuntimeError
- [x] availability rules

```bash
pytest tests/engines/test_whisper_engine.py -v
```

## Edge Cases
- OpenAI rejects files over 25 MB; the error moves to the next model and
  finally raises. Chunking long audio is out of scope.

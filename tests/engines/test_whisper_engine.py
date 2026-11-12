"""Whisper audio engine (DOCFOLD-18)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from docfold.engines.base import OutputFormat
from docfold.engines.whisper_engine import WhisperEngine


class Caller:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    async def __call__(self, **kwargs):
        self.calls.append({**kwargs, "file_name": kwargs["file"].name,
                           "head": kwargs["file"].read(4)})
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


@pytest.fixture
def audio(tmp_path):
    p = tmp_path / "call.wav"
    p.write_bytes(b"RIFFxxxxWAVE")
    return str(p)


async def test_transcribes_with_injected_caller(audio):
    c = Caller([SimpleNamespace(text="Hello, this is a test.")])
    res = await WhisperEngine(atranscription=c).process(audio)
    assert res.content == "Hello, this is a test."
    assert res.engine_name == "whisper"
    assert res.metadata["model"] == "whisper-1"
    assert c.calls[0]["model"] == "whisper-1"
    assert c.calls[0]["file_name"].endswith("call.wav") and c.calls[0]["head"] == b"RIFF"


async def test_json_output_and_dict_response(audio):
    c = Caller([{"text": "Привет"}])
    res = await WhisperEngine(atranscription=c).process(audio, output_format=OutputFormat.JSON)
    assert json.loads(res.content) == {"text": "Привет"}


async def test_fallback_chain(audio):
    c = Caller([RuntimeError("413 too large"), SimpleNamespace(text="ok")])
    eng = WhisperEngine(models=["whisper-1", {"model": "groq/whisper-large-v3", "api_key": "k"}],
                        atranscription=c)
    res = await eng.process(audio)
    assert res.content == "ok" and res.metadata["model"] == "groq/whisper-large-v3"
    assert c.calls[1]["api_key"] == "k"
    with pytest.raises(RuntimeError, match="down"):
        await WhisperEngine(atranscription=Caller([RuntimeError("down")])).process(audio)


def test_availability(monkeypatch):
    assert WhisperEngine(atranscription=Caller([])).is_available()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert not WhisperEngine().is_available()
    assert {"mp3", "wav", "m4a"} <= WhisperEngine().supported_extensions

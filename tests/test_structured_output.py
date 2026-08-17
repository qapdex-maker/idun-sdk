"""Tests for structured output: --json on ask/shell, schema command, Completion.to_dict."""
import json

import pytest

import idun_multi as M
import idun.providers as P
from idun.providers import Completion


@pytest.fixture(autouse=True)
def _no_live(monkeypatch):
    monkeypatch.setenv("IDUN_BASE", "https://test.invalid")
    monkeypatch.setenv("IDUN_PROJECT", "test-project")
    monkeypatch.setenv("IDUN_TENANT", "00000000-0000-0000-0000-000000000000")


def _fake_complete(monkeypatch, text="hello world", model="test-model"):
    def fake(pid, prompt, **kw):
        return Completion(text=text, model=model, provider=pid,
                          prompt_tokens=3, completion_tokens=2, latency_ms=42)
    monkeypatch.setattr(P, "complete", fake)


def test_completion_to_dict_and_roundtrip():
    c = Completion(text="x", model="m", provider="groq",
                   prompt_tokens=1, completion_tokens=2, latency_ms=9)
    d = c.to_dict()
    assert d == {"provider": "groq", "model": "m", "text": "x",
                 "prompt_tokens": 1, "completion_tokens": 2,
                 "total_tokens": 3, "latency_ms": 9}
    back = Completion.from_dict(d)
    assert back.text == "x" and back.total_tokens == 3


def test_ask_json_emits_completion_shape(monkeypatch, capsys):
    _fake_complete(monkeypatch)
    args = M.build_parser().parse_args(
        ["-p", "groq", "ask", "hi", "--json"])
    rc = M.cmd_ask(args)
    assert rc == 0
    out = capsys.readouterr().out
    obj = json.loads(out)
    assert obj["provider"] == "groq"
    assert obj["text"] == "hello world"
    assert obj["total_tokens"] == 5


def test_ask_raw_still_plain(monkeypatch, capsys):
    _fake_complete(monkeypatch)
    args = M.build_parser().parse_args(["-p", "groq", "ask", "hi", "--raw"])
    rc = M.cmd_ask(args)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "hello world"


def test_schema_command_outputs_json(monkeypatch, capsys):
    _fake_complete(monkeypatch)
    args = M.build_parser().parse_args(["-p", "groq", "schema"])
    rc = M.cmd_schema(args)
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["provider"] == "groq"
    assert obj["json_mode_supported"] is True
    assert "response" in obj and "text" in obj["response"]


def test_ask_json_parseable_even_when_streaming(monkeypatch, capsys):
    # streaming path should also produce parseable JSON, not the raw text
    def fake_stream(pid, prompt, **kw):
        def gen():
            yield "par"
            yield "tial"
        return gen()
    monkeypatch.setattr(P, "complete", fake_stream)
    args = M.build_parser().parse_args(
        ["-p", "groq", "ask", "hi", "--stream", "--json"])
    rc = M.cmd_ask(args)
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["text"] == "partial"
    assert obj["streamed"] is True

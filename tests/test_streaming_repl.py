"""Tests for streaming (SSE) and the interactive REPL.

Both are exercised offline: streaming by feeding a fake SSE byte stream into
the urllib opener, the REPL by driving it with a patched stdin/stdout.
"""
import json
from typing import cast

import idun.providers as P
import idun_multi as M


class _FakeResponse:
    """Wraps a byte buffer to look like urllib's context manager."""
    def __init__(self, data: bytes):
        self._data = data
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self, n=-1):
        if n == -1:
            out, self._data = self._data, b""
            return out
        out, self._data = self._data[:n], self._data[n:]
        return out


def _sse_bytes(deltas):
    out = []
    for d in deltas:
        obj = {"choices": [{"delta": {"content": d}}]}
        out.append(f"data: {json.dumps(obj)}\n\n")
    out.append("data: [DONE]\n\n")
    return "".join(out).encode("utf-8")


def test_stream_openai_yields_chunks(monkeypatch):
    import os
    os.environ["NOUS_API_KEY"] = "k"
    payload = _sse_bytes(["Hello", "world", "!"])

    def fake_urlopen(req, timeout=0):
        assert json.loads(req.data.decode())["stream"] is True
        return _FakeResponse(payload)
    monkeypatch.setattr(P.urllib.request, "urlopen", fake_urlopen)

    gen = P.complete("nous", "hi", stream=True)
    chunks = list(cast("list[str]", gen))
    assert chunks == ["Hello", "world", "!"]
    del os.environ["NOUS_API_KEY"]


def test_stream_falls_back_for_non_openai(monkeypatch):
    # A non-openai transport (here: anthropic) with stream=True must still
    # return a generator yielding the full response as a single chunk.
    monkeypatch.setattr(P, "_TRANSPORTS", {
        **P._TRANSPORTS,
        "anthropic": lambda *a, **k: {"content": [{"type": "text", "text": "full answer"}],
                                       "usage": {"input_tokens": 1,
                                                 "output_tokens": 1}},
    })

    class FakeP:
        id = "x"
        transport = "anthropic"
        needs_key = False
        base = "http://x/v1"
        def resolved_model(self): return "m"
        def resolved_base(self): return "http://x/v1"
    monkeypatch.setattr(P, "get_provider", lambda pid: FakeP())
    monkeypatch.setattr(P, "resolve_credential", lambda p: "")
    gen = P.complete("x", "hi", stream=True)
    chunks = list(cast("list[str]", gen))
    assert chunks == ["full answer"]


def test_ask_stream_flag(capsys, monkeypatch):
    captured = {}
    def fake(req, timeout=0):
        captured["stream"] = json.loads(req.data.decode())["stream"]
        return _FakeResponse(_sse_bytes(["a", "b", "c"]))
    monkeypatch.setattr(P.urllib.request, "urlopen", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    args = type("A", (), {"prompt": ["hi"], "provider": "openai", "model": "",
        "system": "", "resume": "", "save_history": "", "temperature": 0.7,
        "max_tokens": 1024, "timeout": 120, "stream": True, "raw": True})()
    assert M.cmd_ask(args) == 0
    assert captured["stream"] is True
    assert "abc" in capsys.readouterr().out


def test_shell_commands_and_history(tmp_path, monkeypatch, capsys):
    import os
    os.environ["OPENAI_API_KEY"] = "k"  # any key so complete() passes the gate
    hist_path = tmp_path / "sess.json"

    # drive the shell with scripted stdin lines + a fake non-streaming complete
    scripted = [
        "first question",
        "/model gpt-4o-mini",
        "second question",
        "/save",            # saves to --save path
        "/quit",
    ]
    monkeypatch.setattr("builtins.input", lambda prompt: scripted.pop(0))
    seen = {}
    monkeypatch.setattr(M.P, "complete",
        lambda pid, prompt, **k: seen.update(k) or M.P.Completion(
            text=f"ans:{prompt}", model="m", provider=pid,
            prompt_tokens=1, completion_tokens=1, latency_ms=1))

    args = type("A", (), {"provider": "openai", "model": "", "system": "",
        "resume": "", "save": str(hist_path), "stream": False,
        "timeout": 120})()
    assert M.cmd_shell(args) == 0

    # history persisted with both turns
    saved = json.loads(hist_path.read_text())
    roles = [m["role"] for m in saved["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    # model override was threaded into the second call
    assert seen["model"] == "gpt-4o-mini"
    # slash commands did NOT become prompts
    assert "first question" in [m["content"] for m in saved["messages"]]
    del os.environ["OPENAI_API_KEY"]

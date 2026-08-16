"""Tests for the nous provider entry and conversation resume.

Both are exercised offline by monkeypatching the transport layer in
idun.providers, so no network or API key is required.
"""
import json

import idun.providers as P


def test_nous_provider_registered():
    p = P.get_provider("nous")
    assert p.transport == "openai"
    assert p.base == "https://api.nousresearch.com/v1"
    assert "NOUS_API_KEY" in p.env_keys
    # free models present
    assert "hermes-3-llama-3.1-8b" in p.models
    assert "deephermes-3-mistral-24b-preview" in p.models
    assert p.resolved_base() == "https://api.nousresearch.com/v1"


def test_nous_base_override():
    import os
    os.environ["IDUN_NOUS_BASE"] = "https://proxy.local/v1"
    try:
        assert P.get_provider("nous").resolved_base() == "https://proxy.local/v1"
    finally:
        del os.environ["IDUN_NOUS_BASE"]


def test_resume_builds_message_list():
    history = [{"role": "user", "content": "hi"},
               {"role": "assistant", "content": "hello"}]
    msgs = P._build_messages("be brief", "again?", history)
    assert msgs[0] == {"role": "system", "content": "be brief"}
    assert msgs[1] == {"role": "user", "content": "hi"}
    assert msgs[2] == {"role": "assistant", "content": "hello"}
    assert msgs[-1] == {"role": "user", "content": "again?"}


def test_resume_normalizes_unknown_roles():
    history = [{"role": "tool", "content": "x"}]
    msgs = P._build_messages("", "go", history)
    # unknown role falls back to user so providers accept it
    assert msgs[0]["role"] == "user"
    assert msgs[-1] == {"role": "user", "content": "go"}


def test_resume_dropped_system_for_anthropic():
    history = [{"role": "user", "content": "hi"}]
    msgs = P._build_messages("sys", "go", history, drop_system=True)
    assert all(m["role"] != "system" for m in msgs)
    assert msgs[-1] == {"role": "user", "content": "go"}


def test_complete_passes_history_to_transport(monkeypatch):
    import os
    os.environ["NOUS_API_KEY"] = "test-key"
    captured = {}

    def fake_openai(p, prompt, model, token, *, system="", temperature=0.7,
                    max_tokens=1024, timeout=120, history=None):
        captured["history"] = history
        captured["messages"] = [{"role": "user", "content": prompt}]
        return {"choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setattr(P, "_TRANSPORTS", {**P._TRANSPORTS, "openai": fake_openai})
    hist = [{"role": "user", "content": "prev"}]
    c = P.complete("nous", "next", history=hist)
    assert c.text == "ok"
    assert captured["history"] == hist
    del os.environ["NOUS_API_KEY"]


def test_cli_ask_resume_and_save(tmp_path, monkeypatch, capsys):
    import idun_multi as M

    path = tmp_path / "chat.json"
    # first turn: save history
    monkeypatch.setattr(M.P, "complete", lambda *a, **k: M.P.Completion(
        text="answer-1", model="m", provider="nous",
        prompt_tokens=1, completion_tokens=1, latency_ms=1))
    args = type("A", (), {
        "prompt": ["hello"], "provider": "nous", "model": "", "system": "",
        "temperature": 0.7, "max_tokens": 1024, "timeout": 120,
        "resume": "", "save_history": str(path), "raw": True, "stream": False})()
    assert M.cmd_ask(args) == 0
    saved = json.loads(path.read_text())
    assert saved["messages"][0]["role"] == "user"
    assert saved["messages"][0]["content"] == "hello"
    assert saved["messages"][-1]["content"] == "answer-1"

    # second turn: resume from the saved file
    seen = {}
    monkeypatch.setattr(M.P, "complete",
                        lambda pid, prompt, **k: seen.update(k) or M.P.Completion(
                            text="answer-2", model="m", provider="nous",
                            prompt_tokens=1, completion_tokens=1, latency_ms=1))
    args2 = type("A", (), {
        "prompt": ["follow up"], "provider": "nous", "model": "", "system": "",
        "temperature": 0.7, "max_tokens": 1024, "timeout": 120,
        "resume": str(path), "save_history": "", "raw": True, "stream": False})()
    assert M.cmd_ask(args2) == 0
    # history was threaded back in: prior user + prior assistant
    assert seen["history"][0]["content"] == "hello"
    assert seen["history"][1]["content"] == "answer-1"
    assert seen["history"][-1]["role"] == "assistant"

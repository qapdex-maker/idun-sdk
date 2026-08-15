"""Tests for the multi-backend dispatch and config (offline, no live calls)."""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idun.client import IdunClient
from idun import backends as be


def test_backend_default_is_azure():
    c = IdunClient(token="x")
    assert c.backend == "azure"


def test_backend_from_env(monkeypatch):
    monkeypatch.setenv("IDUN_BACKEND", "hf")
    c = IdunClient(token="x")
    assert c.backend == "hf"


def test_invalid_backend_rejected():
    import pytest
    with pytest.raises(ValueError):
        IdunClient(backend="nope")


def test_valid_backends_are_azure_hf_github():
    assert be.VALID_BACKENDS == ("azure", "hf", "github")


def test_env_overrides_for_models(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "microsoft/phi-2")
    monkeypatch.setenv("GITHUB_MODEL", "gpt-4o")
    c = IdunClient(backend="hf")
    assert c.hf_model == "microsoft/phi-2"
    assert c.github_model == "gpt-4o"


def test_run_external_hf_shape(monkeypatch):
    captured = {}

    def fake(prompt, token, model, timeout=120, max_new_tokens=1024):
        captured["prompt"] = prompt
        captured["model"] = model
        return f"answer for {prompt}", model

    monkeypatch.setattr(be, "complete_hf", fake)
    text, model = be.run_external("hf", "hi", hf_token="t", hf_model="microsoft/phi-2")
    assert text == "answer for hi"
    assert model == "microsoft/phi-2"
    assert captured["model"] == "microsoft/phi-2"


def test_run_external_github_requires_token():
    import pytest
    with pytest.raises(RuntimeError):
        # no token -> should refuse before any network call
        be.run_external("github", "hi", github_token="")


def test_run_external_unknown_backend():
    import pytest
    with pytest.raises(ValueError):
        be.run_external("ollama", "hi")


def test_complete_hf_returns_idunresult(monkeypatch):
    def fake(prompt, token, model, timeout=120, max_new_tokens=1024):
        return "hf answer", model

    monkeypatch.setattr(be, "complete_hf", fake)
    c = IdunClient(backend="hf", hf_token="t", hf_model="microsoft/phi-2")
    res = c.complete("hello")
    assert res.text == "hf answer"
    assert res.model == "microsoft/phi-2"
    # non-azure backends have no tool-agent trajectory
    assert res.steps == []


def test_complete_messages_flattens_to_last_user(monkeypatch):
    seen = {}

    def fake(prompt, token, model, timeout=120, max_new_tokens=1024):
        seen["prompt"] = prompt
        return "ok", model

    monkeypatch.setattr(be, "complete_hf", fake)
    c = IdunClient(backend="hf", hf_token="t", hf_model="m")
    msgs = [
        {"role": "user", "content": [{"type": "input_text", "text": "first"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "a1"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "second"}]},
    ]
    c.complete_messages(msgs)
    assert seen["prompt"] == "second"


def test_cli_status_runs(capsys):
    from idun_cli import cmd_status
    import argparse
    args = argparse.Namespace()
    # azure default, no token file side effects
    cmd_status(args)
    out = capsys.readouterr().out
    assert "active backend" in out

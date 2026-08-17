"""Tests for the multi-backend / provider-registry dispatch (offline, no live calls).

After the backends.py retirement (v0.2.7) the IdunClient non-azure path is
served by idun.providers.complete(), so these tests exercise that bridge:
backend validation, env model overrides, and the IdunResult shape returned by
the legacy IdunClient for external providers.
"""
import argparse

import idun_cli as cli
from idun import IdunClient
from idun import providers as P


def test_backend_default_is_azure():
    c = IdunClient()
    assert c.backend == "azure"


def test_invalid_backend_rejected():
    import pytest
    with pytest.raises(ValueError):
        IdunClient(backend="nope")


def test_github_alias_resolves_to_openai():
    c = IdunClient(backend="github")
    # 'github' is a legacy alias for the openai transport
    assert c.backend == "openai"


def test_env_overrides_for_models(monkeypatch):
    monkeypatch.setenv("HF_MODEL", "microsoft/phi-2")
    # github is an alias for the openai transport, so OPENAI_MODEL applies
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    c = IdunClient(backend="hf")
    assert c.hf_model == "microsoft/phi-2"
    c2 = IdunClient(backend="github")
    assert c2.openai_model == "gpt-4o"


def test_provider_registry_has_expected_ids():
    ids = {p.id for p in P.list_providers()}
    for expected in ("azure", "hf", "openai", "anthropic", "nous"):
        assert expected in ids


def test_complete_hf_returns_idunresult(monkeypatch):
    """IdunClient(backend=hf).complete routes through providers.complete."""

    def fake_complete(pid, prompt, **kw):
        return P.Completion(text="hf answer", model=kw.get("model", "m"),
                             provider=pid)

    monkeypatch.setattr(P, "complete", fake_complete)
    c = IdunClient(backend="hf", hf_model="microsoft/phi-2")
    res = c.complete("hello")
    assert res.text == "hf answer"
    assert res.model == "microsoft/phi-2"
    # non-azure backends have no tool-agent trajectory
    assert res.steps == []


def test_complete_messages_flattens_to_last_user():
    msgs = [
        {"role": "user", "content": [{"type": "input_text", "text": "first"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "a1"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "second"}]},
    ]
    # extract_last_user is the helper used by complete_messages
    assert P.extract_last_user(msgs) == "second"


def test_cli_status_runs(capsys):
    from idun_cli import cmd_status
    args = argparse.Namespace()
    # azure default, no token file side effects
    cmd_status(args)
    err = capsys.readouterr().err
    assert "active backend" in err


def test_cli_login_saves_via_provider_registry(monkeypatch, capsys):
    saved = {}

    def fake_save(p, tok):
        saved["pid"] = p.id
        saved["tok"] = tok
        return "/tmp/fake"

    monkeypatch.setattr(cli, "save_credential", fake_save)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("hf_secret\n"))
    cli.cmd_login(argparse.Namespace(backend="hf"))
    assert saved["pid"] == "hf"
    assert saved["tok"] == "hf_secret"

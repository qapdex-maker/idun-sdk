"""Regression: `idun chat`/`idun login` without --backend must honor
IDUN_BACKEND / IDUN_PROVIDER, not silently force the azure/Foundry login.

Fix in v0.2.3: --backend default changed from "azure" to None, and _client/_run
resolve the real backend from the environment before falling back to azure.
"""
import io
import os

import idun_cli as cli


class _StubClient:
    def __init__(self, backend=None, token=None, **kw):
        self.backend = backend or os.environ.get("IDUN_BACKEND") \
            or os.environ.get("IDUN_PROVIDER") or "azure"

    def complete(self, prompt, **kw):
        return type("R", (), {"text": f"[{self.backend}] {prompt}",
                              "model": "m", "steps": []})()


def _fake_args(backend=None):
    class A:
        pass
    a = A()
    a.backend = backend
    a.prompt = "hi"
    a.max_tokens = 16
    a.async_ = False
    return a


def test_chat_without_backend_arg_uses_idun_backend(monkeypatch):
    monkeypatch.setenv("IDUN_BACKEND", "hf")
    monkeypatch.setattr(cli, "IdunClient", _StubClient)
    res = cli._run(_fake_args(backend=None), "hello")
    assert res.text == "[hf] hello"


def test_chat_idun_provider_env_wins(monkeypatch):
    monkeypatch.setenv("IDUN_PROVIDER", "github")
    monkeypatch.delenv("IDUN_BACKEND", raising=False)
    monkeypatch.setattr(cli, "IdunClient", _StubClient)
    res = cli._run(_fake_args(backend=None), "hello")
    assert res.text == "[github] hello"


def test_explicit_backend_flag_still_wins(monkeypatch):
    monkeypatch.setenv("IDUN_BACKEND", "hf")
    monkeypatch.setattr(cli, "IdunClient", _StubClient)
    res = cli._run(_fake_args(backend="openai"), "hello")
    assert res.text == "[openai] hello"


def test_login_without_flag_uses_idun_backend(monkeypatch, capsys):
    monkeypatch.setenv("IDUN_BACKEND", "hf")
    monkeypatch.setattr("sys.stdin", io.StringIO("hf_test_tok\n"))
    called = {}
    monkeypatch.setattr(cli, "save_credential",
                        lambda p, tok: called.setdefault("tok", tok))
    # azure do_login must NOT run for hf
    monkeypatch.setattr(cli, "do_login",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("azure login must not run for hf")))
    cli.cmd_login(_fake_args(backend=None))
    assert called.get("tok") == "hf_test_tok"

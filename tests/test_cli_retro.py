"""Retro UI for the legacy `idun` CLI (idun._cli_retro + idun_cli wiring).

Verifies that idun's commands render through the shared 16-bit chrome and
write to stderr (so stdout stays clean for piping), and that status/chat/trace
pick up the env backend instead of always azure.
"""

import idun_cli as cli
import idun._cli_retro as UI


def test_banner_renders_logo(capsys):
    UI.banner()
    err = capsys.readouterr().err
    assert "IDUN" in err
    assert "Azure AI Foundry console" in err


def test_status_out_renders_box(capsys):
    UI.status_out("hf", [("active backend", "hf"), ("hf token", "present")])
    err = capsys.readouterr().err
    assert "hf" in err


def test_chat_out_writes_to_stderr(capsys):
    UI.chat_out("hello world", model="m", backend="hf")
    cap = capsys.readouterr()
    assert "hello world" in cap.err
    assert cap.out == ""  # stdout stays clean for piping


def test_idun_status_respects_idun_backend_env(monkeypatch, capsys):
    monkeypatch.setenv("IDUN_BACKEND", "hf")
    monkeypatch.delenv("IDUN_PROVIDER", raising=False)
    # avoid touching the real token file
    monkeypatch.setattr(cli.backends, "load_hf_token", lambda: "tok")
    cli.cmd_status(type("A", (), {})())
    err = capsys.readouterr().err
    assert "hf" in err
    assert "active backend" in err


def test_idun_status_falls_back_to_azure_when_no_env(monkeypatch, capsys):
    monkeypatch.delenv("IDUN_BACKEND", raising=False)
    monkeypatch.delenv("IDUN_PROVIDER", raising=False)
    # azure path reads token meta; stub it
    monkeypatch.setattr(cli, "_load_meta", lambda: None)
    cli.cmd_status(type("A", (), {})())
    err = capsys.readouterr().err
    assert "azure" in err


def test_cli_retro_module_importable():
    # importing must not require a TTY or any backend
    assert hasattr(UI, "banner")
    assert hasattr(UI, "chat_out")
    assert hasattr(UI, "trace_out")
    assert hasattr(UI, "status_out")

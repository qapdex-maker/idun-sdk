"""Offline tests for idun.welcome (no cmatrix spawn, no network, no TTY).

Covers the two real bugs reported from Termux:

1. Terminal-state break: cmatrix hid the cursor (?25l) and could leave the
   alternate screen active, so after `idun welcome` the shell prompt came back
   but input was invisible ("bash is broken"). The fix is a *hard* reset
   (?25h + ?1049l + 2J + H + 0m + RIS) emitted both after cmatrix and in a
   finally block around the wizard.

2. `idun welcome` should drop straight into the setup wizard.

The ascii art (own block banner + world-tree motif) must render even when
cmatrix is unavailable / non-interactive.
"""
import io
import sys

import idun.welcome as welcome


def _run_show(force_cmatrix, monkeypatch, cap_fd=None):
    calls = {"cmatrix": 0, "reset": 0}

    def fake_run_cmatrix():
        calls["cmatrix"] += 1

    def fake_hard_reset():
        calls["reset"] += 1
        sys.stdout.write("\033[?25h\033[?1049l\033[2J\033[H\033[0m\033c")

    monkeypatch.setattr(welcome, "_run_cmatrix", fake_run_cmatrix)
    monkeypatch.setattr(welcome, "_hard_reset", fake_hard_reset)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        welcome.show_welcome(force_cmatrix=force_cmatrix)
    finally:
        sys.stdout = old
    return buf.getvalue(), calls


def test_hard_reset_emits_cursor_show_and_ris(monkeypatch, capsys):
    welcome._hard_reset()
    out = capsys.readouterr().out
    assert "\033[?25h" in out, "must show the cursor again"
    assert "\033[?1049l" in out, "must leave the alternate screen"
    assert "\033[2J" in out, "must clear the screen"
    assert "\033[H" in out, "must home the cursor"
    assert "\033[0m" in out, "must reset colour"
    assert "\033c" in out, "must emit a full RIS reset (nuclear fallback)"


def test_show_welcome_forces_reset_after_cmatrix(monkeypatch):
    out, calls = _run_show(force_cmatrix=True, monkeypatch=monkeypatch)
    assert calls["cmatrix"] == 1, "cmatrix must run once"
    assert calls["reset"] >= 1, "hard reset must run (the fix)"
    # banner + tree art present
    assert "NatureLM-Idun-5-MoE" in out
    assert "idun-sdk" in out
    # block-letter wordmark: the IDUN art uses these anchor glyphs
    assert "___    ___" in out and "|_ _|" in out
    # the world-tree motif uses box-drawing slashes
    assert "\\||/" in out or "\\____/" in out or "_\\/_" in out


def test_show_welcome_renders_art_without_cmatrix(monkeypatch):
    out, calls = _run_show(force_cmatrix=False, monkeypatch=monkeypatch)
    assert calls["cmatrix"] == 0, "no cmatrix in non-interactive mode"
    assert calls["reset"] >= 1
    assert "NatureLM-Idun-5-MoE" in out
    assert "idun-sdk" in out


def test_show_welcome_then_wizard_invokes_cmd_wizard(monkeypatch, capsys):
    # stub cmatrix + reset so nothing touches the terminal
    monkeypatch.setattr(welcome, "_run_cmatrix", lambda: None)
    monkeypatch.setattr(welcome, "_hard_reset", lambda: None)
    # stub the wizard so we just confirm it is called and the shell stays clean
    called = {}

    def fake_wizard(args):
        called["yes"] = True
        # mimic the real wizard writing its intro + asking (would block on TTY)
        raise EOFError("simulated non-tty input")
    monkeypatch.setattr("idun_cli.cmd_wizard", fake_wizard)
    # idun_cli imports welcome; patch the attribute it will look up
    import idun_cli
    monkeypatch.setattr(idun_cli, "cmd_wizard", fake_wizard)

    # should not raise even though the wizard bails on EOF
    welcome.show_welcome_then_wizard(object())
    assert called.get("yes") is True, "wizard must be invoked by show_welcome_then_wizard"

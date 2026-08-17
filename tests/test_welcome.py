"""Offline tests for idun.welcome (no cmatrix spawn, no network, no TTY).

Covers the real bug reported from Termux:

1. Terminal-state break: cmatrix hid the cursor (?25l) and could leave the
   alternate screen active, so after `idun welcome` the shell prompt came back
   but input was invisible ("bash is broken"). The fix is a *hard* reset
   (?25h + ?1049l + 2J + H + 0m + RIS) emitted both after cmatrix and at the
   end of show_welcome().

2. `idun welcome` must NOT auto-launch the setup wizard. The wizard lives at
   the standalone `idun wizard` command; show_welcome() only renders the
   banner (+ optional matrix). show_welcome_then_wizard was removed.

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
    # banner + tree scene present
    assert "NatureLM-Idun-5-MoE" in out
    assert "idun-sdk" in out
    # block-letter wordmark: the IDUN art uses these anchor glyphs
    assert "___    ___" in out and "|_ _|" in out
    # the new world-tree scene: centred ascii with IDUN in the trunk
    assert "the world-tree" in out
    assert "| IDUN|" in out
    assert "\\__/" in out or "____|____" in out  # roots/base of the tree


def test_show_welcome_renders_art_without_cmatrix(monkeypatch):
    out, calls = _run_show(force_cmatrix=False, monkeypatch=monkeypatch)
    assert calls["cmatrix"] == 0, "no cmatrix in non-interactive mode"
    assert calls["reset"] >= 1
    assert "NatureLM-Idun-5-MoE" in out
    assert "idun-sdk" in out


def test_show_welcome_does_not_launch_wizard(monkeypatch):
    """The welcome screen must render only; no wizard import / call.
    (regression guard for the removed broken redirect)
    """
    monkeypatch.setattr(welcome, "_run_cmatrix", lambda: None)
    monkeypatch.setattr(welcome, "_hard_reset", lambda: None)
    import idun_cli
    # ensure the now-removed symbol is gone and cmd_welcome only renders
    assert not hasattr(welcome, "show_welcome_then_wizard"), \
        "show_welcome_then_wizard must be removed (no redirect)"
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        welcome.show_welcome(force_cmatrix=True)
    finally:
        sys.stdout = old
    assert "the world-tree" in buf.getvalue()
    # the welcome command path must not import cmd_wizard from welcome
    assert "cmd_wizard" not in welcome.__all__

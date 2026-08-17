"""Offline tests for idun.welcome (no cmatrix, no network, no TTY).

Covers:
1. `idun welcome` must render the ASCII banner (block wordmark + world-tree
   scene) and leave the shell usable — no external `cmatrix` dependency, no
   cursor-hide / stuck alternate screen. The hard reset (?25h + ?1049l + 2J
   + H + 0m + RIS) is emitted at the end of show_welcome().
2. `idun welcome` must NOT auto-launch the setup wizard. The wizard lives at
   the standalone `idun wizard` command; show_welcome() only renders the
   banner. (show_welcome_then_wizard was removed.)
"""
import io
import sys

import idun.welcome as welcome


def _run_show(monkeypatch):
    """Render the welcome with the hard reset stubbed so nothing touches the
    real terminal, and return the captured output + reset call count."""
    calls = {"reset": 0}

    def fake_hard_reset():
        calls["reset"] += 1
        sys.stdout.write("\033[?25h\033[?1049l\033[2J\033[H\033[0m\033c")

    monkeypatch.setattr(welcome, "_hard_reset", fake_hard_reset)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        welcome.show_welcome()
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


def test_show_welcome_renders_art(monkeypatch):
    out, calls = _run_show(monkeypatch)
    # banner + tree scene present
    assert "NatureLM-Idun-5-MoE" in out
    assert "idun-sdk" in out
    # block-letter wordmark: the IDUN art uses these anchor glyphs
    assert "___    ___" in out and "|_ _|" in out
    # the world-tree scene: centred ascii with IDUN in the trunk
    assert "the world-tree" in out
    assert "| IDUN|" in out
    assert "____|____" in out  # roots/base of the tree


def test_show_welcome_forces_hard_reset(monkeypatch):
    out, calls = _run_show(monkeypatch)
    assert calls["reset"] >= 1, "hard reset must run (shell stays usable)"
    # no leftover matrix colour escape / cmatrix invocation markers
    assert "cmatrix" not in out


def test_show_welcome_does_not_launch_wizard(monkeypatch):
    """The welcome screen must render only; no wizard import / call.
    (regression guard for the removed broken redirect)
    """
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        welcome.show_welcome()
    finally:
        sys.stdout = old
    assert "the world-tree" in buf.getvalue()
    # the welcome command path must not import cmd_wizard from welcome
    assert "cmd_wizard" not in welcome.__all__


def test_maybe_welcome_shows_once(monkeypatch, tmp_path):
    """maybe_welcome must show the banner on first call and stay silent after."""
    flag = tmp_path / ".idun_sdk_firstrun"
    monkeypatch.setattr(welcome, "_FLAG", str(flag))
    monkeypatch.setattr(welcome, "_hard_reset", lambda: None)

    # first call renders
    buf = io.StringIO()
    sys.stdout = buf
    try:
        welcome.maybe_welcome()
    finally:
        sys.stdout = sys.__stdout__
    first = buf.getvalue()
    assert "the world-tree" in first
    assert flag.exists(), "first-run flag must be written"

    # second call renders nothing
    buf2 = io.StringIO()
    sys.stdout = buf2
    try:
        welcome.maybe_welcome()
    finally:
        sys.stdout = sys.__stdout__
    assert "the world-tree" not in buf2.getvalue(), \
        "must not show again once the flag exists"

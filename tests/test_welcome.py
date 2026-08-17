"""Offline tests for idun.welcome (no cmatrix spawn, no network).

Covers the bug where, on a TTY, cmatrix leaves a frozen frame behind when
killed by the timeout, painting over the ASCII-art banner so only the two
bright text lines survived. The fix (a) does NOT use cmatrix -s (screensaver
mode restores the *original* main screen on a clean key exit, which can drop
our banner), (b) forces a screen reset after cmatrix returns, and (c) clears
+ homes the cursor again before printing the banner so it always lands on a
visible main screen.
"""
import io
import sys

import idun.welcome as welcome


def _run_show(force_cmatrix, monkeypatch, cap_fd):
    """Call show_welcome with cmatrix stubbed out; return captured stdout."""
    calls = {"cmatrix": 0, "reset": 0}

    def fake_run_cmatrix():
        calls["cmatrix"] += 1

    def fake_reset():
        calls["reset"] += 1
        # emulate the real reset exactly as the module writes it
        sys.stdout.write("\033[?1049l\033[2J\033[H\033[0m")

    monkeypatch.setattr(welcome, "_run_cmatrix", fake_run_cmatrix)
    monkeypatch.setattr(welcome, "_reset_screen", fake_reset)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        welcome.show_welcome(force_cmatrix=force_cmatrix)
    finally:
        sys.stdout = old
    return buf.getvalue(), calls


def test_reset_screen_emits_alternate_screen_leave(monkeypatch, capsys):
    welcome._reset_screen()
    out = capsys.readouterr().out
    assert "\033[?1049l" in out, "must leave the cmatrix alternate screen"
    assert "\033[2J" in out, "must clear the screen"
    assert "\033[H" in out, "must home the cursor"
    assert "\033[0m" in out, "must reset color"


def test_show_welcome_forces_reset_after_cmatrix(monkeypatch):
    out, calls = _run_show(force_cmatrix=True, monkeypatch=monkeypatch, cap_fd=None)
    assert calls["cmatrix"] == 1, "cmatrix must run once"
    assert calls["reset"] == 1, "screen reset must run once (the fix)"
    # banner must be present and printed AFTER the reset sequence
    reset_idx = out.index("\033[?1049l")
    banner_idx = out.index("___ _    ___")
    assert banner_idx > reset_idx, "banner must come after the reset"
    assert "NatureLM-Idun-5-MoE" in out
    assert "idun-sdk" in out
    # all 4 ASCII-art lines present
    for line in (" |_ _| |  |_ _|", "  | || |__ | ||", "|___|____|___|"):
        assert line in out, f"missing banner line: {line!r}"


def test_show_welcome_no_cmatrix_when_noninteractive(monkeypatch):
    out, calls = _run_show(force_cmatrix=False, monkeypatch=monkeypatch, cap_fd=None)
    assert calls["cmatrix"] == 0, "no cmatrix in non-interactive mode"
    assert calls["reset"] == 0, "no reset needed when cmatrix did not run"
    assert "NatureLM-Idun-5-MoE" in out
    assert "idun-sdk" in out

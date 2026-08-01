#!/usr/bin/env python3
"""First-run welcome for the Idun SDK CLI.

Shows the Idun banner and, when `cmatrix` is available on PATH, a short
purple-tinted matrix flourish as an Easter egg. Everything here is
optional and degrades silently: no external dependency, no crash if
`cmatrix` is missing or the terminal is non-interactive.

Public API:
    maybe_welcome()  -> call once at CLI startup; shows the welcome at most
                        once per user (guarded by a flag file).
    show_welcome()   -> always show it (used by `idun welcome`).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

__all__ = ["maybe_welcome", "show_welcome"]

# Flag file so the matrix/welcome only appears on the very first run after
# a fresh `pip install`. Lives in the user's home, not the package dir.
_FLAG = os.path.join(os.path.expanduser("~"), ".idun_sdk_firstrun")

# Idun brand (matches Foundry-dark UI: purple #8b5cf6 / blue #3b82f6).
_BANNER = (
    "\033[38;5;141m"
    "  ___ _    ___ _  _  _   _ _____ _    ___\n"
    " |_ _| |  |_ _| \\| |/ \\| | |_   _| |  | __|\n"
    "  | || |__ | || .` / _ \\ |   | | | |__| _|\n"
    " |___|____|___|_|\\/_/ \\_\\_|  |_| |____|___|\n"
    "\033[0m"
    "  \033[38;5;57mNatureLM-Idun-5-MoE  ·  Azure AI Foundry\033[0m\n"
    "  \033[38;5;141midun-sdk\033[0m — thin client + CLI (stdlib-only)\n"
)

# cmatrix colour closest to the Idun purple (#8b5cf6). "magenta" reads best
# on dark terminals; fall back to "blue" if you prefer the Azure tint.
_CMATRIX_COLOR = "magenta"
_CMATRIX_SECONDS = 3


def _cmatrix_available() -> bool:
    return shutil.which("cmatrix") is not None


def _shown_before() -> bool:
    try:
        return os.path.exists(_FLAG)
    except OSError:
        return False


def _mark_shown() -> None:
    try:
        with open(_FLAG, "w", encoding="utf-8") as f:
            f.write("1\n")
    except OSError:
        pass


def _run_cmatrix() -> None:
    """Best-effort short matrix flourish. Never raises."""
    if not _cmatrix_available():
        return
    # -s screensaver mode (exits on first keystroke); -u delay; -C colour.
    cmd = ["cmatrix", "-s", "-u", "4", "-C", _CMATRIX_COLOR]
    try:
        # Screensaver mode bails on any key; we also cap with a hard timeout
        # so non-interactive/CI runs never hang.
        subprocess.run(cmd, timeout=_CMATRIX_SECONDS + 2,
                       check=False, stdin=sys.stdin)
    except Exception:
        # Any failure (missing binary, no tty, alarm) -> just skip it.
        pass


def show_welcome(force_cmatrix: bool = False) -> None:
    """Print the Idun banner, optionally preceded by the matrix flourish."""
    interactive = sys.stdout.isatty()
    if interactive or force_cmatrix:
        _run_cmatrix()
    sys.stdout.write(_BANNER)
    sys.stdout.write("\n")
    sys.stdout.flush()


def maybe_welcome() -> None:
    """Show the welcome once per user, then never again."""
    if _shown_before():
        return
    show_welcome()
    _mark_shown()


if __name__ == "__main__":
    show_welcome(force_cmatrix=True)

#!/usr/bin/env python3
"""First-run welcome + setup for the Idun SDK CLI.

Shows an ASCII-art Idun banner (a world-tree / "tree of knowledge" motif in
the brand purple), a short optional cmatrix flourish as an Easter egg, and a
hard terminal reset afterwards so the shell is never left in a broken state
(cursor hidden / alternate screen stuck). Everything degrades silently: no
external dependency, no crash if `cmatrix` is missing or the terminal is
non-interactive.

Public API:
    maybe_welcome()  -> call once at CLI startup; shows the welcome at most
                        once per user (guarded by a flag file).
    show_welcome()   -> always show it (used by `idun welcome`).
    show_welcome_then_wizard(args) -> welcome, then drop straight into the
                        setup wizard (used by `idun welcome`).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

__all__ = ["maybe_welcome", "show_welcome", "show_welcome_then_wizard"]

# Flag file so the matrix/welcome only appears on the very first run after
# a fresh `pip install`. Lives in the user's home, not the package dir.
_FLAG = os.path.join(os.path.expanduser("~"), ".idun_sdk_firstrun")

# Idun brand (matches Foundry-dark UI: purple #8b5cf6 / blue #3b82f6).
_PURPLE = "\033[38;5;141m"
_BLUE = "\033[38;5;57m"
_CYAN = "\033[38;5;51m"
_GREEN = "\033[38;5;48m"
_GOLD = "\033[38;5;221m"
_RESET = "\033[0m"

# Block-letter IDUN wordmark (figlet-ish, fixed width). Coloured line by line.
_IDUN_ART = (
    r"  ___    ___  _   _  _   _  _____  ___  ___  ___  " + "\n"
    r" |_ _|  / _ \| \| |/ \| |/ \| |_   _|/ _ \|   \| __| " + "\n"
    r"  | |  | | | | .` |  _  |  _  |  | | | | | | |) | _|  " + "\n"
    r" |___|  \___/|_|\/_|_|\/_|_|\_\ |_|  \___/|_|\_\___| "
)

# A small "world tree / tree of knowledge" motif under the wordmark — the
# Idun (Norse: "the one who sets in motion") myth, rendered in ANSI box art.
_TREE_ART = (
    "        " + _GREEN + r"    \||/    " + _RESET + "\n"
    "        " + _GREEN + r"     --o--    " + _RESET + "\n"
    "        " + _GREEN + r"   \  ||  /   " + _RESET + "\n"
    "    " + _CYAN + r"_\/_   ||   _/_/" + _RESET + "\n"
    "   " + _CYAN + r"/  \  ||  /  " + "\\" + _RESET + "\n"
    "  " + _GOLD + r"(    )  ||  (    )" + _RESET + "\n"
    "   " + _GOLD + r"\____/ || \____/" + _RESET + "\n"
    "        " + _BLUE + r"    ||     " + _RESET + "\n"
    "        " + _BLUE + r"  ============= " + _RESET
)

_SUBTITLE = (
    _BLUE + "NatureLM-Idun-5-MoE" + _RESET
    + "  ·  " + _PURPLE + "Azure AI Foundry" + _RESET
)
_TAGLINE = (
    _PURPLE + "idun-sdk" + _RESET
    + " — thin client + CLI (stdlib-only)"
)

# cmatrix colour closest to the Idun purple (#8b5cf6). "magenta" reads best
# on dark terminals; fall back to "blue" if you prefer the Azure tint.
_CMATRIX_COLOR = "magenta"
_CMATRIX_SECONDS = 2


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
    # Only animate on a real terminal. Under pytest / CI, stdout is a redirect
    # (not a tty), so cmatrix would run the full timeout and hang the suite.
    if not sys.stdout.isatty():
        return
    # Plain mode (NOT -s screensaver): -s restores the *original* main screen on
    # a clean key exit, which can drop our banner. Plain alternate-screen mode
    # returns to the main screen cleanly on SIGTERM/timeout.
    cmd = ["cmatrix", "-u", "4", "-C", _CMATRIX_COLOR]
    try:
        subprocess.run(cmd, timeout=_CMATRIX_SECONDS + 2,
                       check=False, stdin=sys.stdin)
    except Exception:
        pass


def _hard_reset() -> None:
    """Fully restore the terminal to a usable interactive state.

    cmatrix hides the cursor (?25l) and may leave the alternate screen buffer
    active when killed by our timeout. If we don't undo BOTH, the shell prompt
    comes back but is invisible / input echo is gone — exactly the "bash is
    broken after idun welcome" symptom. We send, in order:

      ?25h  show cursor
      ?1049l leave alternate screen
      2J    clear screen
      H     move cursor home
      0m    reset colour/attributes
      \\033c RIS full reset — the nuclear option that restores every terminal
            mode (cursor, alt screen, mouse tracking, keypad) to defaults.
    """
    try:
        sys.stdout.write("\033[?25h\033[?1049l\033[2J\033[H\033[0m\033c")
        sys.stdout.flush()
    except Exception:
        pass


def _print_welcome_art() -> None:
    """Emit the ASCII banner (own art, not just cmatrix) on a clean screen."""
    # Guarantee a clean, visible main screen before we draw.
    sys.stdout.write("\033[2J\033[H\033[?25h")
    sys.stdout.write("\n")
    for line in _IDUN_ART.splitlines():
        sys.stdout.write("  " + line + "\n")
    sys.stdout.write("\n")
    for line in _TREE_ART.splitlines():
        sys.stdout.write(line + "\n")
    sys.stdout.write("\n")
    sys.stdout.write("  " + _SUBTITLE + "\n")
    sys.stdout.write("  " + _TAGLINE + "\n")
    sys.stdout.write("\n")
    sys.stdout.flush()


def show_welcome(force_cmatrix: bool = False) -> None:
    """Print the Idun ASCII banner, optionally preceded by a matrix flourish."""
    interactive = sys.stdout.isatty()
    if interactive or force_cmatrix:
        _run_cmatrix()
        _hard_reset()          # undo cmatrix's cursor-hide / alt-screen
    _print_welcome_art()       # draw on a guaranteed-clean, visible screen
    _hard_reset()              # final guarantee: cursor visible, shell usable


def show_welcome_then_wizard(args) -> None:
    """Welcome, then drop straight into the setup wizard.

    The hard terminal reset is guaranteed in a ``finally`` block so the shell
    is never left with a hidden cursor / stuck alternate screen, even if the
    wizard is aborted (Ctrl-C / EOF) or raises.
    """
    from idun_cli import cmd_wizard
    try:
        show_welcome(force_cmatrix=True)
        return cmd_wizard(args)
    except (EOFError, KeyboardInterrupt):
        # user bailed out of the wizard — fine, just leave a clean shell
        return
    finally:
        _hard_reset()


def maybe_welcome() -> None:
    """Show the welcome once per user, then never again."""
    if _shown_before():
        return
    show_welcome()
    _mark_shown()


if __name__ == "__main__":
    show_welcome(force_cmatrix=sys.stdout.isatty())

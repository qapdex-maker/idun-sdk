#!/usr/bin/env python3
"""First-run welcome + setup for the Idun SDK CLI.

Shows an ASCII-art Idun banner (a world-tree / "tree of knowledge" motif in
the brand purple), and guarantees the shell is left usable afterwards (cursor
visible, no stuck alternate screen). Pure stdlib, no external dependencies, no
crash when the terminal is non-interactive.

Public API:
    maybe_welcome()  -> call once at CLI startup; shows the welcome at most
                        once per user (guarded by a flag file).
    show_welcome()   -> always show it (used by `idun welcome`). The matching
                        setup wizard lives at the standalone `idun wizard`
                        command and is never auto-launched from here, so the
                        welcome can never redirect into an interactive prompt.
"""
from __future__ import annotations

import os
import sys

__all__ = ["maybe_welcome", "show_welcome"]
_COLOR_CODE = {
    "purple": "\033[38;5;141m",
    "blue": "\033[38;5;57m",
    "cyan": "\033[38;5;51m",
    "green": "\033[38;5;48m",
    "gold": "\033[38;5;221m",
}

# Flag file so the welcome only appears on the very first run after
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

# A larger "world tree of knowledge" (Yggdrasil) scene. Each tuple is
# (plain ascii line, colour key). Rendered centred so it never goes ragged
# on narrow Termux windows. No line ends in a backslash (raw-string safety).
_TREE_SCENE = [
    (r"          .    *    .    *    .    ", "green"),
    (r"        *     the world-tree     * ", "green"),
    (r"            |    *    |    *    |   ", "green"),
    (r"           /|\   |   /|\   |   /|\ ", "green"),
    (r"          / | \  |  / | \  |  / | \ ", "green"),
    (r"         /  |  \ | /  |  \ | /  |  \ ", "green"),
    (r"        /   |   \|/   |   \|/   |   \ ", "green"),
    (r"       /    |    |    |    |    |    \ ", "purple"),
    (r"      /     |    |    |    |    |     \ ", "purple"),
    (r"     (      | IDUN|    | IDUN|      ) ", "purple"),
    (r"      \     |    |    |    |    |     / ", "purple"),
    (r"       \    |    |    |    |    |    / ", "purple"),
    (r"        \   |    |    |    |    |   / ", "purple"),
    (r"         \  |    |    |    |    |  / ", "purple"),
    (r"          \ |    |    |    |    | / ", "purple"),
    (r"           \|    |    |    |    |/ ", "purple"),
    (r"            |    |    |    |    |   ", "purple"),
    (r"        ____|____|____|____|____   ", "gold"),
    (r"       /    |    |    |    |    \  ", "gold"),
    (r"      /     |    |    |    |     \ ", "gold"),
    (r"     /  __  |    |    |    |  __  \ ", "gold"),
    (r"    |  |  | |    |    |    |  |  | | ", "gold"),
    (r"    |  |__| |    |    |    |  |__| | ", "gold"),
    (r"     \  \__/     |    |     \__/  /  ", "gold"),
]

_SUBTITLE = (
    _BLUE + "NatureLM-Idun-5-MoE" + _RESET
    + "  ·  " + _PURPLE + "Azure AI Foundry" + _RESET
)
_TAGLINE = (
    _PURPLE + "idun-sdk" + _RESET
    + " — thin client + CLI (stdlib-only)"
)

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


def _hard_reset() -> None:
    """Fully restore the terminal to a usable interactive state.

    Guarantees the cursor is visible and no alternate screen is left stuck
    (in case any prior program left the terminal in a broken state). We send,
    in order:

      ?25h  show cursor
      ?1049l leave alternate screen
      2J    clear screen
      H     move cursor home
      0m    reset colour/attributes
      \033c RIS full reset — restores every terminal mode to defaults.
    """
    try:
        sys.stdout.write("\033[?25h\033[?1049l\033[2J\033[H\033[0m\033c")
        sys.stdout.flush()
    except Exception:
        pass


def _print_welcome_art() -> None:
    """Emit the ASCII banner on a clean screen.

    Everything is left-aligned with a fixed 2-space indent (no terminal-width
    centring). Left-aligned art stays flush at every width, including narrow
    Termux windows where the reported terminal width is unreliable.
    """
    sys.stdout.write("\033[2J\033[H\033[?25h")
    sys.stdout.write("\n")
    for line in _IDUN_ART.splitlines():
        sys.stdout.write("  " + line + "\n")
    sys.stdout.write("\n")
    _print_tree_scene()
    sys.stdout.write("\n")
    sys.stdout.write("  " + _SUBTITLE + "\n")
    sys.stdout.write("  " + _TAGLINE + "\n")
    sys.stdout.write("\n")
    sys.stdout.flush()


def _print_tree_scene() -> None:
    """Render the world-tree scene, left-aligned with a fixed indent.

    Fixed indent (not centred) so the wordmark, tree and subtitle all start on
    the same column regardless of the (often-wrong) reported terminal width.
    """
    indent = "  "  # 2 spaces, matches the wordmark + subtitle indent
    for line, color in _TREE_SCENE:
        code = _COLOR_CODE.get(color, "")
        sys.stdout.write(indent + code + line + _RESET + "\n")


def show_welcome() -> None:
    """Print the Idun ASCII banner and guarantee a usable shell afterwards."""
    _print_welcome_art()       # draw on a guaranteed-clean, visible screen
    _hard_reset()              # final guarantee: cursor visible, shell usable


def maybe_welcome() -> None:
    """Show the welcome once per user, then never again."""
    if _shown_before():
        return
    show_welcome()
    _mark_shown()


if __name__ == "__main__":
    show_welcome()

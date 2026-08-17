"""16-bit retro terminal chrome for the Idun CLI.

Pure-stdlib ANSI rendering in the spirit of the 1990s console era: a fixed
16-colour SNES/Amiga-ish palette, double-line box drawing, chunky headers,
scanline dividers and a blocky loading bar. No third-party dependencies, and
every effect degrades to plain ASCII when the output is not a TTY or when
``NO_COLOR`` / ``IDUN_NO_RETRO`` is set.
"""
from __future__ import annotations

import os
import shutil
import sys
import time

# --------------------------------------------------------------------------
# Capability detection
# --------------------------------------------------------------------------


def color_enabled(stream=None) -> bool:
    """True when ANSI colour should be emitted."""
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("IDUN_NO_RETRO"):
        return False
    if os.environ.get("IDUN_FORCE_COLOR"):
        return True
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def width(default: int = 64) -> int:
    """Usable terminal width, clamped to a retro-friendly range."""
    try:
        cols = shutil.get_terminal_size((default, 24)).columns
    except OSError:
        cols = default
    return max(40, min(cols, 100))


# --------------------------------------------------------------------------
# Palette — the classic 16 console colours
# --------------------------------------------------------------------------

_CODES = {
    "reset": "0",
    "bold": "1",
    "dim": "2",
    "black": "30", "red": "31", "green": "32", "yellow": "33",
    "blue": "34", "magenta": "35", "cyan": "36", "white": "37",
    "bright_black": "90", "bright_red": "91", "bright_green": "92",
    "bright_yellow": "93", "bright_blue": "94", "bright_magenta": "95",
    "bright_cyan": "96", "bright_white": "97",
    "bg_blue": "44", "bg_magenta": "45", "bg_black": "40",
}

# semantic roles, mapped onto the 16-colour palette
ROLE = {
    "frame": "bright_magenta",
    "title": "bright_cyan",
    "accent": "bright_yellow",
    "ok": "bright_green",
    "warn": "bright_yellow",
    "err": "bright_red",
    "muted": "bright_black",
    "text": "white",
}

# -------------------------------------------------------------------------
# Theme system (v0.5) — selectable retro palettes via IDUN_THEME.
# Each theme is a full ROLE mapping. The default is the original 16-colour
# "classic" palette above; the others evoke a specific machine.
# -------------------------------------------------------------------------

THEMES = {
    "classic": dict(ROLE),  # the original 16-colour SNES/Amiga-ish palette
    "c64": {
        # Commodore 64: blue background, light-blue frame, cyan text
        "frame": "bright_blue",
        "title": "bright_cyan",
        "accent": "bright_yellow",
        "ok": "bright_green",
        "warn": "bright_yellow",
        "err": "bright_red",
        "muted": "bright_black",
        "text": "bright_cyan",
    },
    "gameboy": {
        # Game Boy DMG-01: four-shade green-on-green (mapped to ANSI greens)
        "frame": "green",
        "title": "bright_green",
        "accent": "bright_yellow",
        "ok": "bright_green",
        "warn": "yellow",
        "err": "bright_red",
        "muted": "bright_black",
        "text": "green",
    },
    "amiga": {
        # Amiga Workbench: blue title bar feel, white text
        "frame": "blue",
        "title": "bright_white",
        "accent": "bright_cyan",
        "ok": "bright_green",
        "warn": "yellow",
        "err": "bright_red",
        "muted": "bright_black",
        "text": "white",
    },
    "cga": {
        # IBM CGA: magenta/cyan on black, the classic 80s PC look
        "frame": "magenta",
        "title": "cyan",
        "accent": "bright_white",
        "ok": "bright_green",
        "warn": "bright_yellow",
        "err": "bright_red",
        "muted": "bright_black",
        "text": "bright_white",
    },
}

_ACTIVE_THEME = "classic"


def list_themes() -> list[str]:
    """Available theme ids (pass one to ``set_theme`` or ``IDUN_THEME``)."""
    return sorted(THEMES)


def set_theme(name: str) -> str:
    """Activate a theme by id; falls back to 'classic' for unknown ids.

    Returns the actually-active theme id (handy for confirming a typo-safe
    default). Honours ``IDUN_THEME`` only at module import time via
    ``_apply_env_theme()``; this function is the explicit override.
    """
    global _ACTIVE_THEME, ROLE
    key = (name or "").strip().lower()
    if key not in THEMES:
        key = "classic"
    _ACTIVE_THEME = key
    ROLE = dict(THEMES[key])
    return _ACTIVE_THEME


def theme() -> str:
    """Currently active theme id."""
    return _ACTIVE_THEME


def _apply_env_theme() -> None:
    """Pick up IDUN_THEME at import so `export IDUN_THEME=gameboy` just works."""
    env = os.environ.get("IDUN_THEME")
    if env:
        set_theme(env)


_apply_env_theme()


def paint(text: str, *roles: str, stream=None) -> str:
    """Wrap text in ANSI codes for the given roles/colour names."""
    if not roles or not color_enabled(stream):
        return text
    seq = []
    for r in roles:
        name = ROLE.get(r, r)
        code = _CODES.get(name)
        if code:
            seq.append(code)
    if not seq:
        return text
    return f"\033[{';'.join(seq)}m{text}\033[0m"


def strip_len(text: str) -> int:
    """Visible length of a string that may contain ANSI sequences."""
    out, i = 0, 0
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            if j == -1:
                break
            i = j + 1
            continue
        out += 1
        i += 1
    return out


# --------------------------------------------------------------------------
# Box drawing — double lines for that DOS/Amiga feel
# --------------------------------------------------------------------------

BOX = {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "h": "═", "v": "║",
       "lt": "╠", "rt": "╣"}
ASCII_BOX = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|",
             "lt": "+", "rt": "+"}


def _glyphs() -> dict:
    if os.environ.get("IDUN_ASCII"):
        return ASCII_BOX
    return BOX


def rule(w: int | None = None, role: str = "frame") -> str:
    """A full-width scanline divider."""
    g = _glyphs()
    w = w or width()
    return paint(g["h"] * w, role)


def box(lines: list[str], title: str = "", w: int | None = None,
        role: str = "frame") -> str:
    """Render text lines inside a double-line box with an optional title.

    When ``w`` is omitted the box grows to fit its widest line (accounting for
    ANSI sequences), capped at the terminal width.
    """
    g = _glyphs()
    # explode embedded newlines so multi-line payloads never break the frame
    flat: list[str] = []
    for ln in lines:
        flat.extend(str(ln).replace("\t", "  ").split("\n"))
    lines = flat
    if w is None:
        content = max([strip_len(x) for x in lines] + [len(title) + 6])
        w = min(width(), content + 4)
        w = max(w, 24)
    inner = w - 2
    out = []
    if title:
        label = f" {title} "
        pad = inner - len(label)
        left = 2
        right = max(0, pad - left)
        out.append(paint(g["tl"] + g["h"] * left, role)
                   + paint(label, "title", "bold")
                   + paint(g["h"] * right + g["tr"], role))
    else:
        out.append(paint(g["tl"] + g["h"] * inner + g["tr"], role))
    for ln in lines:
        visible = strip_len(ln)
        if visible > inner - 2:
            ln = ln[: inner - 5] + "..."
            visible = strip_len(ln)
        out.append(paint(g["v"], role) + " " + ln
                   + " " * (inner - visible - 2) + " "
                   + paint(g["v"], role))
    out.append(paint(g["bl"] + g["h"] * inner + g["br"], role))
    return "\n".join(out)


def header(title: str, subtitle: str = "") -> str:
    """A chunky title bar."""
    w = width()
    bar = paint(" " + title.upper().center(w - 2) + " ",
                "bg_blue", "bright_white", "bold")
    lines = [bar]
    if subtitle:
        lines.append(paint(subtitle.center(w), "muted"))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# The logo — blocky 16-bit lettering
# --------------------------------------------------------------------------

LOGO = r"""
 ██╗██████╗ ██╗   ██╗███╗   ██╗
 ██║██╔══██╗██║   ██║████╗  ██║
 ██║██║  ██║██║   ██║██╔██╗ ██║
 ██║██║  ██║██║   ██║██║╚██╗██║
 ██║██████╔╝╚██████╔╝██║ ╚████║
 ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝
"""

LOGO_ASCII = r"""
  _   _____   _   _   _  _
 | | |  _  \ | | | | | \| |
 | | | | | | | | | | |  ' |
 |_| |_____/  \___/  |_|\_|
"""


def logo(version: str = "") -> str:
    """The Idun wordmark, colour-cycled across the 16-colour palette."""
    art = LOGO_ASCII if os.environ.get("IDUN_ASCII") else LOGO
    cycle = ("bright_magenta", "magenta", "bright_blue", "bright_cyan",
             "bright_cyan", "bright_green")
    out = []
    for i, line in enumerate(art.strip("\n").split("\n")):
        out.append(paint(line, cycle[i % len(cycle)]))
    tag = "MULTI-PROVIDER LLM CONSOLE"
    if version:
        tag += f"  ·  v{version}"
    out.append("")
    out.append(paint("   " + tag, "accent", "bold"))
    return "\n".join(out)


# --------------------------------------------------------------------------
# Progress / status widgets
# --------------------------------------------------------------------------

BLOCKS = "░▒▓█"


def bar(fraction: float, w: int = 24, role: str = "ok") -> str:
    """A blocky 16-bit style progress bar."""
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(fraction * w))
    if os.environ.get("IDUN_ASCII"):
        body = "#" * filled + "." * (w - filled)
    else:
        body = "█" * filled + "░" * (w - filled)
    return paint("[", "muted") + paint(body, role) + paint("]", "muted") \
        + f" {int(fraction * 100):3d}%"


class Spinner:
    """Minimal retro spinner usable as a context manager."""

    FRAMES = ("◐", "◓", "◑", "◒")
    ASCII_FRAMES = ("|", "/", "-", "\\")

    def __init__(self, label: str = "working", stream=None) -> None:
        self.label = label
        self.stream = stream or sys.stdout
        self._i = 0
        self.active = color_enabled(self.stream)

    def tick(self) -> None:
        if not self.active:
            return
        frames = (self.ASCII_FRAMES if os.environ.get("IDUN_ASCII")
                  else self.FRAMES)
        ch = frames[self._i % len(frames)]
        self._i += 1
        self.stream.write("\r" + paint(ch, "accent") + " "
                          + paint(self.label, "muted") + "   ")
        self.stream.flush()

    def done(self, msg: str = "") -> None:
        if self.active:
            self.stream.write("\r" + " " * (len(self.label) + 12) + "\r")
            self.stream.flush()
        if msg:
            print(msg)

    def __enter__(self) -> "Spinner":
        self.tick()
        return self

    def __exit__(self, *exc) -> None:
        self.done()


def status(kind: str, msg: str) -> str:
    """A prefixed status line: ok / warn / err / info."""
    marks = {"ok": ("[ OK ]", "ok"), "warn": ("[WARN]", "warn"),
             "err": ("[FAIL]", "err"), "info": ("[ .. ]", "title")}
    label, role = marks.get(kind, marks["info"])
    return paint(label, role, "bold") + " " + msg


def table(rows: list[tuple], headers: tuple = (), role: str = "title") -> str:
    """Render a simple aligned table with a retro underline."""
    if not rows:
        return paint("(empty)", "muted")
    cols = len(rows[0])
    widths = [0] * cols
    all_rows = ([headers] if headers else []) + [tuple(map(str, r)) for r in rows]
    for r in all_rows:
        for i, cell in enumerate(r[:cols]):
            widths[i] = max(widths[i], strip_len(str(cell)))
    out = []
    if headers:
        line = "  ".join(str(h).upper().ljust(widths[i])
                         for i, h in enumerate(headers[:cols]))
        out.append(paint(line, role, "bold"))
        out.append(paint("─" * strip_len(line) if not os.environ.get("IDUN_ASCII")
                         else "-" * strip_len(line), "muted"))
    for r in rows:
        cells = []
        for i, cell in enumerate(tuple(map(str, r))[:cols]):
            # pad by VISIBLE width so ANSI-coloured cells stay aligned
            cells.append(cell + " " * max(0, widths[i] - strip_len(cell)))
        out.append("  ".join(cells).rstrip())
    return "\n".join(out)


def typewriter(text: str, delay: float = 0.004, stream=None) -> None:
    """Print text with a retro typewriter cadence (skipped when not a TTY)."""
    stream = stream or sys.stdout
    if not color_enabled(stream) or os.environ.get("IDUN_NO_TYPEWRITER"):
        stream.write(text + "\n")
        return
    for ch in text:
        stream.write(ch)
        stream.flush()
        if ch not in " \n":
            time.sleep(delay)
    stream.write("\n")


__all__ = ["paint", "box", "rule", "header", "logo", "bar", "Spinner",
           "status", "table", "typewriter", "width", "color_enabled", "ROLE"]

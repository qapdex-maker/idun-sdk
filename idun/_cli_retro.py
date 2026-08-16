"""Retro chrome for the legacy ``idun`` CLI (Azure-Foundry-first client).

Keeps the 16-bit look consistent with ``idun-multi`` by wrapping the plain
``print`` calls in idun_cli.py with the shared ``idun.retro`` helpers. Small,
focused helpers so idun_cli.py stays readable and testable.

Degrades to plain text when stdout is not a TTY or when ``NO_COLOR`` /
``IDUN_NO_RETRO`` is set (handled inside ``idun.retro``).
"""
from __future__ import annotations

import sys

from . import retro as R


def banner() -> None:
    """Print the ASCII logo + a one-line subtitle."""
    print(R.logo(), file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)
    print(R.header("IDUN", "Azure AI Foundry console"), file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)


def chat_out(text: str, model: str = "", backend: str = "") -> None:
    """Render a chat/trace answer in a retro response box + typewriter."""
    meta = " · ".join(p for p in (backend, model) if p)
    print(R.header("IDUN RESPONSE", meta), file=sys.stderr)
    R.typewriter(text, stream=sys.stderr)
    print(file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)


def trace_out(res, backend: str = "azure") -> None:
    """Render an agent trace (reasoning + tool steps) in retro chrome."""
    print(R.header("AGENT TRACE", f"{backend} · {len(res.steps)} steps"),
          file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)
    for i, s in enumerate(res.steps, 1):
        if s.kind == "tool":
            print(R.status("info",
                  f"{i:>2}. TOOL   web_search  [{s.status}]"), file=sys.stderr)
            print(f"        query: {s.query}", file=sys.stderr)
        else:
            head = s.text.replace("\n", " ").strip()[:90]
            label = "REASON" if s.kind == "reasoning" else "MSG"
            print(R.status("info",
                  f"{i:>2}. {label}  {head}{'…' if len(s.text) > 90 else ''}"),
                  file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)
    print(R.paint("FINAL ANSWER:", "accent"), file=sys.stderr)
    R.typewriter(res.text, stream=sys.stderr)
    print(file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)


def status_out(backend: str, lines: list[tuple[str, str]]) -> None:
    """Render `idun status` as a retro box.

    ``lines`` is a list of (label, value) pairs, e.g. ("hf token", "present").
    The active backend is shown in the box header; the body lines are the
    credential state, not a repeat of the backend name.
    """
    body = [f"{R.paint(label, 'title')}: {value}" for label, value in lines]
    print(R.header("IDUN STATUS", backend), file=sys.stderr)
    print(R.box(body, title="BACKEND", w=48), file=sys.stderr)


def info(msg: str) -> None:
    print(R.status("info", msg), file=sys.stderr)


def ok(msg: str) -> None:
    print(R.status("ok", msg), file=sys.stderr)


def err(msg: str) -> None:
    print(R.status("err", msg), file=sys.stderr)


def wizard_intro(choices: list[str]) -> None:
    print(R.logo(), file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)
    print(R.header("IDUN SETUP WIZARD", "configure a backend"), file=sys.stderr)
    for c in choices:
        print(R.status("info", c), file=sys.stderr)
    print(R.rule(role="frame"), file=sys.stderr)

#!/usr/bin/env python3
"""Idun CLI — terminal client for NatureLM-Idun-5-MoE on Azure AI Foundry.

Usage:
  idun login                 # device-code Entra login -> ~/foundry_token.txt
  idun chat  "your prompt"   # print final answer
  idun trace "your prompt"   # print agent trajectory (reasoning + web_search steps)

Stdlib-only; needs FOUNDRY_TOKEN (from `idun login` or env).
"""
from __future__ import annotations

import argparse
import os
import sys

from idun import IdunClient, login as do_login, load_token


def _client() -> IdunClient:
    tok = load_token() or os.environ.get("FOUNDRY_TOKEN")
    if not tok:
        sys.exit("No token. Run `idun login` first (or export FOUNDRY_TOKEN).")
    return IdunClient(token=tok)


def cmd_login(_args):
    do_login()


def cmd_chat(args):
    c = _client()
    res = c.complete(args.prompt, max_output_tokens=args.max_tokens)
    print(res.text)


def cmd_trace(args):
    c = _client()
    res = c.complete(args.prompt, max_output_tokens=args.max_tokens)
    print(f"Model: {res.model}\n")
    print("AGENT TRACE ({})".format(len(res.steps)))
    print("=" * 60)
    for i, s in enumerate(res.steps, 1):
        if s.kind == "tool":
            print(f"  {i:>2}. TOOL   web_search  [{s.status}]")
            print(f"        query: {s.query}")
        else:
            head = s.text.replace("\n", " ").strip()[:90]
            label = "REASON" if s.kind == "reasoning" else "MSG"
            print(f"  {i:>2}. {label}  {head}{'…' if len(s.text) > 90 else ''}")
    print("=" * 60)
    print("\nFINAL ANSWER:")
    print(res.text)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="idun", description="NatureLM-Idun-5-MoE CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="device-code Entra login").set_defaults(func=cmd_login)

    pc = sub.add_parser("chat", help="print final answer")
    pc.add_argument("prompt")
    pc.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pc.set_defaults(func=cmd_chat)

    pt = sub.add_parser("trace", help="print agent trajectory (steps)")
    pt.add_argument("prompt")
    pt.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pt.set_defaults(func=cmd_trace)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

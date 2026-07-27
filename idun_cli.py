#!/usr/bin/env python3
"""Idun CLI — terminal client for NatureLM-Idun-5-MoE on Azure AI Foundry.

Usage:
  idun login                 # device-code Entra login -> ~/foundry_token.txt
  idun chat  "your prompt"   # print final answer
  idun trace "your prompt"   # print agent trajectory (reasoning + web_search steps)
  idun token [--status|--refresh|-f]   # inspect / rotate the stored token

Stdlib-only; needs FOUNDRY_TOKEN (from `idun login` or env).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from idun import IdunClient, login as do_login, load_token, logo_path
from idun.auth import maybe_refresh, _load_meta, REFRESH_SLACK

BANNER = r"""
 ___    ___  _  _  _   _  _ _  _  _  _  ___  ___  ___
|__ \  / _ \| \| |/_\ | \| | || | \| |/ _ \|   \| __|
  / / | (_) | .` |/ _ \| .` | __ | .` | (_) | |) | _|
 /___| \___/|_|\_/_/ \_\_|\_|_||_|_|\_|\___/|___/|___|
            NatureLM-Idun-5-MoE  ·  Azure AI Foundry
"""


def _client() -> IdunClient:
    tok = load_token() or os.environ.get("FOUNDRY_TOKEN")
    if not tok:
        sys.exit("No token. Run `idun login` first (or export FOUNDRY_TOKEN).")
    return IdunClient(token=tok)


def cmd_login(_args):
    print(BANNER)
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


def cmd_logo(_args):
    print(BANNER)
    print("Logo assets bundled with this package:")
    print(f"  white : {logo_path('white')}")
    print(f"  color : {logo_path('color')}")


def cmd_token(args):
    meta = _load_meta()
    if meta is None:
        sys.exit("No token stored. Run `idun login` first.")
    expires_at = float(meta.get("expires_at", 0))
    remaining = int(expires_at - time.time())
    has_refresh = bool(meta.get("refresh_token"))
    print(f"token len   : {len(meta.get('access_token', ''))}")
    print(f"expires in  : {remaining}s ({'REFRESH PENDING' if remaining <= REFRESH_SLACK else 'ok'})")
    print(f"refresh tok : {'yes' if has_refresh else 'no (device-code fallback)'}")
    if args.refresh or args.force:
        new = maybe_refresh(force=True)
        if new:
            print(f"refreshed -> len {len(new)}")
        else:
            print("refresh returned no token")


def cmd_export(args):
    c = _client()
    res = c.complete(args.prompt, max_output_tokens=args.max_tokens)
    payload = res.to_json() if args.fmt == "json" else res.to_markdown()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"wrote {args.fmt} trace -> {args.output} ({len(res.steps)} steps)")
    else:
        print(payload)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="idun", description="NatureLM-Idun-5-MoE CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="device-code Entra login").set_defaults(func=cmd_login)

    sub.add_parser("logo", help="show bundled Foundry logo paths").set_defaults(func=cmd_logo)

    pc = sub.add_parser("chat", help="print final answer")
    pc.add_argument("prompt")
    pc.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pc.set_defaults(func=cmd_chat)

    pt = sub.add_parser("trace", help="print agent trajectory (steps)")
    pt.add_argument("prompt")
    pt.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pt.set_defaults(func=cmd_trace)

    ptok = sub.add_parser("token", help="inspect / rotate stored token")
    ptok.add_argument("--status", action="store_true", help="show token status (default)")
    ptok.add_argument("--refresh", action="store_true", help="force a token rotation now")
    ptok.add_argument("-f", "--force", action="store_true", dest="force", help="alias for --refresh")
    ptok.set_defaults(func=cmd_token)

    pe = sub.add_parser("export", help="run prompt and save agent trajectory")
    pe.add_argument("prompt")
    pe.add_argument("--format", choices=["json", "md"], default="json", dest="fmt",
                    help="json (full trajectory) or md (human-readable trace doc)")
    pe.add_argument("--output", "-o", help="write to file instead of stdout")
    pe.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pe.set_defaults(func=cmd_export)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

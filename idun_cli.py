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
from idun.client import IdunResult
from idun.auth import maybe_refresh, _load_meta, REFRESH_SLACK
from idun.welcome import maybe_welcome, show_welcome

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


def _run(args, prompt) -> IdunResult:
    """Sync or async completion based on args.async flag (default sync)."""
    c = _client()
    if getattr(args, "async_", False):
        import asyncio
        return asyncio.run(c.complete_async(prompt, max_output_tokens=args.max_tokens))
    return c.complete(prompt, max_output_tokens=args.max_tokens)


def cmd_login(_args):
    print(BANNER)
    do_login()


def cmd_chat(args):
    res = _run(args, args.prompt)
    print(res.text)


def cmd_trace(args):
    res = _run(args, args.prompt)
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


def cmd_welcome(_args):
    show_welcome(force_cmatrix=True)


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
    res = _run(args, args.prompt)
    payload = res.to_json() if args.fmt == "json" else res.to_markdown()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"wrote {args.fmt} trace -> {args.output} ({len(res.steps)} steps)")
    else:
        print(payload)


def cmd_packs(_args):
    from idun import list_packs
    packs = list_packs()
    if not packs:
        print("No prompt packs installed.")
        return
    print("Available prompt packs:\n")
    for pk in packs:
        print(f"  {pk['name']}  ({pk['count']} prompts) — {pk['title']}")
        if pk["description"]:
            print(f"    {pk['description']}")


def cmd_run(args):
    from idun import get_prompt, run_pack
    if args.all:
        if args.key:
            sys.exit("--all and KEY are mutually exclusive")
        results = run_pack(args.pack, keys=None, max_output_tokens=args.max_tokens)
        for key, res in results:
            print(f"\n=== {key} ===")
            print(res.text)
        return
    if not args.key:
        sys.exit("either KEY or --all is required")
    try:
        prompt = get_prompt(args.pack, args.key)
    except (FileNotFoundError, KeyError) as e:
        sys.exit(str(e))
    res = _run(args, prompt)
    print(res.text)


def cmd_diff(args):
    ra = _run(args, args.prompt_a)
    rb = _run(args, args.prompt_b)
    from idun import diff_traces, format_diff
    d = diff_traces(ra, rb)
    print(format_diff(d, args.fmt))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="idun", description="NatureLM-Idun-5-MoE CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="device-code Entra login").set_defaults(func=cmd_login)

    sub.add_parser("logo", help="show bundled Foundry logo paths").set_defaults(func=cmd_logo)

    sub.add_parser("welcome", help="show the Idun welcome (banner + matrix)").set_defaults(func=cmd_welcome)

    pc = sub.add_parser("chat", help="print final answer")
    pc.add_argument("prompt")
    pc.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pc.add_argument("--async", action="store_true", dest="async_",
                    help="use the asyncio variant (run_in_executor, no extra deps)")
    pc.set_defaults(func=cmd_chat)

    pt = sub.add_parser("trace", help="print agent trajectory (steps)")
    pt.add_argument("prompt")
    pt.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pt.add_argument("--async", action="store_true", dest="async_",
                    help="use the asyncio variant (run_in_executor, no extra deps)")
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
    pe.add_argument("--async", action="store_true", dest="async_",
                    help="use the asyncio variant (run_in_executor, no extra deps)")
    pe.set_defaults(func=cmd_export)

    pk = sub.add_parser("packs", help="list available prompt packs")
    pk.set_defaults(func=cmd_packs)

    pr = sub.add_parser("run", help="run a prompt from a pack (or --all for the whole pack)")
    pr.add_argument("pack", help="pack name (e.g. contoso)")
    pr.add_argument("key", nargs="?", default=None,
                    help="prompt key inside the pack (omit with --all to run every prompt)")
    pr.add_argument("--all", action="store_true", dest="all",
                    help="run ALL prompts in the pack (batch)")
    pr.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pr.add_argument("--async", action="store_true", dest="async_",
                    help="use the asyncio variant (run_in_executor, no extra deps)")
    pr.set_defaults(func=cmd_run)

    pd = sub.add_parser("diff", help="compare two prompt trajectories (side-by-side)")
    pd.add_argument("prompt_a", metavar="PROMPT_A")
    pd.add_argument("prompt_b", metavar="PROMPT_B")
    pd.add_argument("--format", choices=["json", "md"], default="md", dest="fmt",
                    help="diff output format (json or human-readable md)")
    pd.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    pd.add_argument("--async", action="store_true", dest="async_",
                    help="use the asyncio variant (run_in_executor, no extra deps)")
    pd.set_defaults(func=cmd_diff)
    return p


def main():
    maybe_welcome()
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

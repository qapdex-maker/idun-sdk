#!/usr/bin/env python3
"""Idun CLI — terminal client for NatureLM-Idun-5-MoE (multi-backend).

Usage:
  idun wizard                 # universal first-run setup (any user, any backend)
  idun login  --backend hf    # store backend credentials
  idun status                 # show active backend + credential state
  idun chat  --backend github "your prompt"   # print final answer
  idun trace "your prompt"    # print agent trajectory (azure only, with steps)
  idun token [--status|--refresh|-f]   # inspect / rotate the stored Azure token

Stdlib-only; each backend has its own credential file (no single secret).
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
from idun import backends

BANNER = r"""
 ___    ___  _  _  _   _  _ _  _  _  _  ___  ___  ___
|__ \  / _ \| \| |/_\ | \| | || | \| |/ _ \|   \| __|
  / / | (_) | .` |/ _ \| .` | __ | .` | (_) | |) | _|
 /___| \___/|_|\_/_/ \_\_|\_|_||_|_|\_|\___/|___/|___|
            NatureLM-Idun-5-MoE  ·  Azure AI Foundry
"""


def _add_backend_arg(p):
    p.add_argument("--backend", choices=["azure", "hf", "github", "openai"],
                   default=None,
                   help="completion backend (default: $IDUN_BACKEND or azure)")


def _add_common_args(p):
    _add_backend_arg(p)
    p.add_argument("--max-tokens", type=int, default=1024, dest="max_tokens")
    p.add_argument("--async", action="store_true", dest="async_",
                   help="use the asyncio variant (no extra deps)")


def _client(backend: str | None = None) -> IdunClient:
    backend = backend or os.environ.get("IDUN_BACKEND") \
        or os.environ.get("IDUN_PROVIDER") or "azure"
    if backend == "azure":
        tok = load_token() or os.environ.get("FOUNDRY_TOKEN")
        if not tok:
            sys.exit("No token. Run `idun login` first (or export FOUNDRY_TOKEN).")
        return IdunClient(token=tok, backend="azure")
    # external backends: no FOUNDRY_TOKEN required
    return IdunClient(backend=backend)


def _run(args, prompt) -> IdunResult:
    """Sync or async completion based on args.async flag (default sync)."""
    c = _client(getattr(args, "backend", None))
    if getattr(args, "async_", False):
        import asyncio
        return asyncio.run(c.complete_async(prompt, max_output_tokens=args.max_tokens))
    return c.complete(prompt, max_output_tokens=args.max_tokens)


def cmd_login(args):
    print(BANNER)
    backend = getattr(args, "backend", None) or os.environ.get("IDUN_BACKEND") \
        or os.environ.get("IDUN_PROVIDER") or "azure"
    if backend == "azure":
        do_login()
        return
    if backend == "hf":
        tok = input("Hugging Face token (hf_...): ").strip()
        if tok:
            from idun.backends import save_hf_token
            save_hf_token(tok)
            print("saved -> ~/hf_token.txt")
        return
    if backend == "github":
        tok = input("GitHub PAT (ghp_... / github_pat_...): ").strip()
        if tok:
            from idun.backends import save_github_token
            save_github_token(tok)
            print("saved -> ~/github_token.txt")
        return
    sys.exit(f"login not supported for backend {backend!r}")


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


def cmd_openapi(args):
    """Print the bundled OpenAPI 3 spec (or its path)."""
    from idun import openapi_path
    if getattr(args, "path", False):
        print(openapi_path())
        return
    with open(openapi_path(), encoding="utf-8") as f:
        print(f.read())


def cmd_welcome(_args):
    show_welcome(force_cmatrix=True)


def cmd_status(_args):
    from idun import backends as be
    backend = os.environ.get("IDUN_BACKEND", "azure")
    print(f"active backend : {backend}")
    if backend == "azure":
        meta = _load_meta()
        ok = bool(meta and meta.get("access_token"))
        print(f"  azure token  : {'present' if ok else 'MISSING (~/foundry_token.txt)'}")
    elif backend == "hf":
        tok = be.load_hf_token()
        print(f"  hf token     : {'present' if tok else 'MISSING'}")
        print(f"  hf model     : {os.environ.get('HF_MODEL') or be.HF_DEFAULT_MODEL}")
    elif backend == "github":
        tok = be.load_github_token()
        print(f"  github token : {'present' if tok else 'MISSING'}")
        print(f"  gh model     : {os.environ.get('GITHUB_MODEL') or be.GITHUB_DEFAULT_MODEL}")
    elif backend == "openai":
        tok = be.load_openai_token()
        print(f"  openai token : {'present' if tok else 'MISSING'}")
        print(f"  openai model : {os.environ.get('OPENAI_MODEL') or be.OPENAI_DEFAULT_MODEL}")
        print(f"  openai base  : {os.environ.get('OPENAI_BASE') or be.OPENAI_DEFAULT_BASE}")


def cmd_hf(args):
    """Hugging Face pipeline: whoami / status / push (stdlib-only)."""
    from idun import hf_pipeline as hf
    token = hf.load_hf_token()
    sub = args.hf_command
    if sub == "whoami":
        if not token:
            print("HF token missing. Set HF_TOKEN or ~/hf_token.txt "
                  "(idun login --backend hf).")
            return 1
        try:
            info = hf.hf_whoami(token)
        except RuntimeError as e:
            print(f"HF whoami failed: {e}")
            return 1
        print(f"HF user : {info.get('name')}  (id {info.get('id')})")
        orgs = [o.get('name') for o in info.get('orgs', [])]
        if orgs:
            print(f"orgs    : {', '.join(orgs)}")
        print(f"email   : {info.get('email') or '(private)'}")
        return 0
    if sub == "status":
        model = args.model
        st = hf.hf_model_status(model, token)
        if st["error"]:
            print(f"{model}: error -> {st['error']}")
            return 1
        if not st["exists"]:
            print(f"{model}: NOT FOUND on the Hub")
            return 1
        gated = st["gated"] or "no"
        print(f"{model}: exists | gated={gated} | private={st['private']} | "
              f"task={st['pipeline_tag'] or 'n/a'}")
        return 0
    if sub == "push":
        if not token:
            print("HF token missing. Set HF_TOKEN or ~/hf_token.txt.")
            return 1
        model = args.model
        files = {}
        for f in args.files:
            try:
                with open(f, encoding="utf-8") as fh:
                    files[os.path.basename(f)] = fh.read()
            except OSError as e:
                print(f"cannot read {f}: {e}")
                return 1
        try:
            commit = hf.hf_upload(model, files, token, private=args.private)
        except RuntimeError as e:
            print(f"HF push failed: {e}")
            return 1
        print(f"pushed {len(files)} file(s) to {model}")
        print(f"commit: {commit.get('commitId', 'n/a')}")
        return 0
    print("unknown hf subcommand")
    return 1


def cmd_wizard(_args):
    """Universal first-run setup: picks a backend, captures creds/config,
    writes ~/.idunrc so every future `idun` call uses it globally."""
    print(BANNER)
    print("Idun Setup Wizard — configure a backend (runs for any user).")
    print("-" * 60)
    print("Available backends:")
    print("  1) azure   — Azure AI Foundry (NatureLM-Idun). Needs an Azure tenant.")
    print("  2) hf      — Hugging Face Inference API (free tier, needs HF token).")
    print("  3) github  — GitHub Models (free tier, needs GitHub PAT).")
    print("  4) openai  — OpenAI-compatible /v1/chat/completions (needs OPENAI_API_KEY).")
    choice = input("Select backend [1-4]: ").strip()
    mapping = {"1": "azure", "2": "hf", "3": "github", "4": "openai"}
    backend = mapping.get(choice, "azure")
    print(f"Selected: {backend}\n")

    cfg = {}
    if backend == "azure":
        print("Azure setup requires a tenant + Foundry resource.")
        print("Run `idun login --backend azure` and complete the device-code flow.")
        print("REQUIRED: no tenant ships with this package — point it at yours:")
        print("  export IDUN_BASE=https://<resource>.services.ai.azure.com")
        print("  export IDUN_PROJECT=<project>")
        print("  export IDUN_AGENT=<agent>          # optional")
        print("  export IDUN_TENANT=<tenant-guid>   # optional")
        cfg["IDUN_BACKEND"] = "azure"
    elif backend == "hf":
        tok = input("Hugging Face token (hf_...) [or blank for anonymous]: ").strip()
        if tok:
            from idun.backends import save_hf_token
            save_hf_token(tok)
        model = input(f"HF model [default: {backends.HF_DEFAULT_MODEL}]: ").strip()
        if model:
            cfg["HF_MODEL"] = model
        cfg["IDUN_BACKEND"] = "hf"
    elif backend == "github":
        tok = input("GitHub PAT (ghp_... / github_pat_...): ").strip()
        if not tok:
            sys.exit("GitHub backend requires a PAT. Aborting.")
        from idun.backends import save_github_token
        save_github_token(tok)
        model = input(f"GitHub model [default: {backends.GITHUB_DEFAULT_MODEL}]: ").strip()
        if model:
            cfg["GITHUB_MODEL"] = model
        cfg["IDUN_BACKEND"] = "github"
    elif backend == "openai":
        tok = input("OpenAI API key (sk-...) [or blank for OPENAI_API_KEY env]: ").strip()
        if tok:
            from idun.backends import save_openai_token
            save_openai_token(tok)
        model = input(f"OpenAI model [default: {backends.OPENAI_DEFAULT_MODEL}]: ").strip()
        if model:
            cfg["OPENAI_MODEL"] = model
        base = input(f"OpenAI base URL [default: {backends.OPENAI_DEFAULT_BASE}]: ").strip()
        if base:
            cfg["OPENAI_BASE"] = base
        cfg["IDUN_BACKEND"] = "openai"

    # write ~/.idunrc (shell env file)
    rc = os.path.join(os.path.expanduser("~"), ".idunrc")
    with open(rc, "a", encoding="utf-8") as f:
        f.write("\n# idun wizard config\n")
        for k, v in cfg.items():
            f.write(f"export {k}={v}\n")
    os.chmod(rc, 0o600)
    print(f"\nWrote config to {rc}")
    print("Source it once:  source ~/.idunrc   (or restart your shell)")
    print("Then:  idun chat \"Hello\"  (uses the configured backend)")


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
            if isinstance(res, Exception):
                print(f"\n=== {key} ===\n[ERROR] {res}")
                continue
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
    p = argparse.ArgumentParser(prog="idun", description="NatureLM-Idun-5-MoE CLI (multi-backend)")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser(
        "login",
        help="store backend credentials",
        description=("Store credentials for a backend.\n\n"
                     "  idun login --backend azure    (device-code Entra login)\n"
                     "  idun login --backend hf       (Hugging Face token)\n"
                     "  idun login --backend github   (GitHub PAT)"),
    )
    _add_backend_arg(pl)
    pl.set_defaults(func=cmd_login)

    sub.add_parser(
        "logo",
        help="show bundled Foundry logo paths",
        description="Print the on-disk paths of the bundled Idun/Foundry logo assets.\n\nExample:\n  idun logo",
    ).set_defaults(func=cmd_logo)

    sub.add_parser(
        "welcome",
        help="show the Idun welcome (banner + matrix)",
        description="Render the Idun welcome screen (banner + matrix rain).\n\nExample:\n  idun welcome",
    ).set_defaults(func=cmd_welcome)

    pw = sub.add_parser(
        "wizard",
        help="universal first-run setup for any user",
        description="Interactive setup wizard: picks a backend, captures creds/config, writes ~/.idunrc so every future `idun` call uses it globally.\n\nExample:\n  idun wizard",
    )
    pw.set_defaults(func=cmd_wizard)

    ps = sub.add_parser(
        "status",
        help="show active backend + credential state",
        description="Print the resolved backend and whether credentials are present (no secret is shown).\n\nExample:\n  idun status",
    )
    ps.set_defaults(func=cmd_status)

    pc = sub.add_parser(
        "chat",
        help="print final answer",
        description="Send a prompt and print only the final answer text.\n\nExample:\n  idun chat \"What is the capital of France?\"\n  idun chat --backend github \"Summarize quantum computing\"\n  idun chat --async \"Explain transformers\"",
    )
    pc.add_argument("prompt")
    _add_common_args(pc)
    pc.set_defaults(func=cmd_chat)

    pt = sub.add_parser(
        "trace",
        help="print agent trajectory (steps)",
        description="Send a prompt and print the full agent trajectory (reasoning + web_search steps). Only meaningful on the azure backend.\n\nExample:\n  idun trace \"What is the capital of France?\"\n  idun trace --backend azure \"Compare Python and Rust\"",
    )
    pt.add_argument("prompt")
    _add_common_args(pt)
    pt.set_defaults(func=cmd_trace)

    ptok = sub.add_parser(
        "token",
        help="inspect / rotate stored token",
        description="Inspect the stored Entra token, or force a rotation.\n\nExample:\n  idun token            # show status\n  idun token --refresh  # force rotate now\n  idun token -f",
    )
    ptok.add_argument("--status", action="store_true", help="show token status (default)")
    ptok.add_argument("--refresh", action="store_true", help="force a token rotation now")
    ptok.add_argument("-f", "--force", action="store_true", dest="force", help="alias for --refresh")
    ptok.set_defaults(func=cmd_token)

    pe = sub.add_parser(
        "export",
        help="run prompt and save agent trajectory",
        description="Run a prompt and export the full agent trajectory to JSON or markdown.\n\nExample:\n  idun export \"What is the capital of France?\" -o trace.md\n  idun export --backend github \"Explain photosynthesis\" -o trace.json\n  idun export --async \"Tell me a joke\" > out.md",
    )
    pe.add_argument("prompt")
    pe.add_argument("--format", choices=["json", "md"], default="json", dest="fmt",
                    help="json (full trajectory) or md (human-readable trace doc)")
    pe.add_argument("--output", "-o", help="write to file instead of stdout")
    _add_common_args(pe)
    pe.set_defaults(func=cmd_export)

    pk = sub.add_parser(
        "packs",
        help="list available prompt packs",
        description="List all bundled prompt packs (name, prompt count, title).\n\nExample:\n  idun packs",
    )
    pk.set_defaults(func=cmd_packs)

    pr = sub.add_parser(
        "run",
        help="run a prompt from a pack (or --all for the whole pack)",
        description="Run a single prompt from a bundled pack, or the whole pack with --all.\n\nExample:\n  idun run contoso esg_check\n  idun run contoso --all\n  idun run contoso sustainability_summary --max-tokens 2048",
    )
    pr.add_argument("pack", help="pack name (e.g. contoso)")
    pr.add_argument("key", nargs="?", default=None,
                    help="prompt key inside the pack (omit with --all to run every prompt)")
    pr.add_argument("--all", action="store_true", dest="all",
                    help="run ALL prompts in the pack (batch)")
    _add_common_args(pr)
    pr.set_defaults(func=cmd_run)

    pd = sub.add_parser(
        "diff",
        help="compare two prompt trajectories (side-by-side)",
        description="Run two prompts and compare their agent trajectories side-by-side.\n\nExample:\n  idun diff \"Capital of France?\" \"Capital of Germany?\"\n  idun diff --format json \"A\" \"B\" > diff.json",
    )
    pd.add_argument("prompt_a", metavar="PROMPT_A")
    pd.add_argument("prompt_b", metavar="PROMPT_B")
    pd.add_argument("--format", choices=["json", "md"], default="md", dest="fmt",
                    help="diff output format (json or human-readable md)")
    _add_common_args(pd)
    pd.set_defaults(func=cmd_diff)

    ph = sub.add_parser(
        "hf",
        help="Hugging Face pipeline: whoami / model status / push to Hub",
        description=("Hugging Face Hub + Inference glue (stdlib-only, no huggingface_hub "
                     "client needed).\n\n"
                     "  idun hf whoami              # validate token, show user\n"
                     "  idun hf status MODEL       # exists? gated? private? task?\n"
                     "  idun hf push MODEL f1 f2   # create repo + upload files"),
    )
    hfsub = ph.add_subparsers(dest="hf_command", required=True)
    hfsub.add_parser("whoami", help="show HF user for the current token")
    pstat = hfsub.add_parser("status", help="probe a model repo on the Hub")
    pstat.add_argument("model", help="e.g. microsoft/phi-3-mini-4k-instruct")
    ppush = hfsub.add_parser("push", help="create a repo and upload files")
    ppush.add_argument("model", help="target repo, e.g. qapdex/my-agent-out")
    ppush.add_argument("files", nargs="+", help="local files to upload")
    ppush.add_argument("--private", action="store_true", help="create a private repo")
    ph.set_defaults(func=cmd_hf)

    po = sub.add_parser(
        "openapi",
        help="print the bundled OpenAPI 3 spec for the completion API",
        description=("Print the bundled OpenAPI 3.0 spec describing Idun's OpenAI-compatible "
                     "completion surface. Pipe to a file or Swagger UI to drive Idun from any "
                     "OpenAPI client.\n\nExample:\n  idun openapi\n  idun openapi > openapi.json"),
    )
    po.add_argument("--path", action="store_true", help="print the on-disk path instead of the spec")
    po.set_defaults(func=cmd_openapi)

    return p


def main():
    maybe_welcome()
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

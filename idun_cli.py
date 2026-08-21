#!/usr/bin/env python3
"""Idun CLI — terminal client for NatureLM-Idun-5-MoE (multi-backend).

Usage:
  idun wizard                 # universal first-run setup (any user, any backend)
  idun login  --backend hf    # store backend credentials
  idun status                 # show active backend + credential state
  idun chat  --backend openai "your prompt"   # print final answer
  idun chat                              # live interactive session (REPL)
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
from idun.welcome import maybe_welcome
from idun.providers import get_provider, save_credential
from idun import _cli_retro as UI


def _save_backend_token(backend: str, token: str) -> str:
    """Persist a non-azure backend key via the provider registry (~/.idun/<id>.token).

    No name rewriting happens here: the backend name IS the provider id. The
    former ``github`` -> ``openai`` mapping meant a GitHub PAT was written into
    OpenAI's token file. Unknown names now raise from get_provider().
    """
    path = save_credential(get_provider(backend), token)
    return path



def _add_backend_arg(p):
    # 'github' is intentionally absent: GitHub Models is a separate service and
    # was previously aliased onto openai, mixing credentials. See
    # tests/test_no_provider_aliasing.py.
    p.add_argument("--backend", choices=["azure", "hf", "openai"],
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
    backend = getattr(args, "backend", None)
    if getattr(args, "async_", False):
        import asyncio
        from idun.async_client import AsyncIdunClient
        from idun.providers import default_provider
        pid = backend or default_provider()
        return asyncio.run(
            AsyncIdunClient().acomplete(
                pid, prompt, max_output_tokens=args.max_tokens))
    c = _client(backend)
    return c.complete(prompt, max_output_tokens=args.max_tokens)


def cmd_login(args):
    UI.banner()
    backend = getattr(args, "backend", None) or os.environ.get("IDUN_BACKEND") \
        or os.environ.get("IDUN_PROVIDER") or "azure"
    if backend == "azure":
        do_login()
        return
    if backend == "hf":
        tok = input("Hugging Face token (hf_...): ").strip()
        if tok:
            _save_backend_token("hf", tok)
            UI.ok("saved -> ~/.idun/hf.token")
        return
    if backend == "github":
        # Previously this asked for a GitHub PAT and stored it in
        # ~/.idun/openai.token, overwriting the OpenAI key and sending the PAT
        # to api.openai.com. GitHub Models is a separate service and is not
        # supported; refuse instead of corrupting another provider's secret.
        sys.exit(
            "backend 'github' is not supported.\n"
            "GitHub Models is a separate service (own endpoint, GitHub PAT as\n"
            "credential). It used to be aliased onto 'openai', which stored the\n"
            "PAT in ~/.idun/openai.token and sent it to api.openai.com.\n"
            "Use --backend openai with an OpenAI key instead."
        )
    sys.exit(f"login not supported for backend {backend!r}")


def cmd_chat(args):
    prompt = " ".join(args.prompt).strip() if isinstance(args.prompt, list) else (args.prompt or "")
    backend = (getattr(args, "backend", None)
               or os.environ.get("IDUN_BACKEND")
               or os.environ.get("IDUN_PROVIDER") or "azure")
    if prompt:
        res = _run(args, prompt)
        UI.chat_out(res.text, model=res.model, backend=backend)
        return
    # No prompt -> live interactive session (running mood, not the help dump).
    UI.chat_intro(backend)
    import signal

    def _quit(_sig, _frm):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, _quit)
    try:
        while True:
            try:
                line = input("idun> ").strip()
            except EOFError:
                print(file=sys.stderr)
                break
            if not line or line.lower() in ("exit", "quit", "q"):
                break
            try:
                res = _run(args, line)
            except (RuntimeError, ValueError) as e:
                UI.err(str(e))
                continue
            UI.chat_out(res.text, model=res.model, backend=backend)
    except KeyboardInterrupt:
        print(file=sys.stderr)
    UI.info("session closed.")


def cmd_trace(args):
    res = _run(args, args.prompt)
    UI.trace_out(res, backend=getattr(args, "backend", None)
                 or os.environ.get("IDUN_BACKEND")
                 or os.environ.get("IDUN_PROVIDER") or "azure")


def cmd_logo(_args):
    UI.banner()
    UI.info("Logo assets bundled with this package:")
    print(f"  white : {logo_path('white')}", file=sys.stderr)
    print(f"  color : {logo_path('color')}", file=sys.stderr)


def cmd_openapi(args):
    """Print the bundled OpenAPI 3 spec (or its path)."""
    from idun import openapi_path
    if getattr(args, "path", False):
        print(openapi_path(), file=sys.stderr)
        return
    with open(openapi_path(), encoding="utf-8") as f:
        print(f.read(), file=sys.stderr)


def cmd_welcome(_args):
    from idun.welcome import show_welcome
    show_welcome()
    UI.info("Run `idun wizard` for first-run setup, or `idun chat` to begin.")
    return 0


def cmd_status(_args):
    from idun.providers import credential_status
    backend = os.environ.get("IDUN_BACKEND",
                os.environ.get("IDUN_PROVIDER", "azure"))
    lines = [("active backend", backend)]
    if backend == "azure":
        meta = _load_meta()
        ok = bool(meta and meta.get("access_token"))
        lines.append(("azure token", "present" if ok else "MISSING (~/foundry_token.txt)"))
    elif backend in ("hf", "openai"):
        p = get_provider(backend)
        status = credential_status(p)
        lines.append((f"{backend} token", status))
        lines.append((f"{backend} model", os.environ.get(
            f"{backend.upper()}_MODEL", p.resolved_model())))
        if backend == "openai":
            lines.append(("openai base", os.environ.get("OPENAI_BASE") or p.resolved_base()))
    UI.status_out(backend, lines)


def cmd_hf(args):
    """Hugging Face pipeline: whoami / status / push (stdlib-only)."""
    from idun import hf_pipeline as hf
    token = hf.load_hf_token()
    sub = args.hf_command
    if sub == "whoami":
        if not token:
            UI.err("HF token missing. Set HF_TOKEN or store it via "
                   "`idun-multi login --backend hf` (writes ~/.idun/hf.token).")
            return 1
        try:
            info = hf.hf_whoami(token)
        except RuntimeError as e:
            UI.err(f"HF whoami failed: {e}")
            return 1
        UI.ok(f"HF user : {info.get('name')}  (id {info.get('id')})")
        orgs = [o.get('name') for o in info.get('orgs', [])]
        if orgs:
            UI.info(f"orgs    : {', '.join(orgs)}")
        UI.info(f"email   : {info.get('email') or '(private)'}")
        return 0
    if sub == "status":
        model = args.model
        st = hf.hf_model_status(model, token)
        if st["error"]:
            UI.err(f"{model}: error -> {st['error']}")
            return 1
        if not st["exists"]:
            UI.err(f"{model}: NOT FOUND on the Hub")
            return 1
        gated = st["gated"] or "no"
        UI.ok(f"{model}: exists | gated={gated} | private={st['private']} | "
              f"task={st['pipeline_tag'] or 'n/a'}")
        return 0
    if sub == "push":
        if not token:
            UI.err("HF token missing. Set HF_TOKEN or store it via "
                   "`idun-multi login --backend hf` (writes ~/.idun/hf.token).")
            return 1
        model = args.model
        files = {}
        for f in args.files:
            try:
                with open(f, encoding="utf-8") as fh:
                    files[os.path.basename(f)] = fh.read()
            except OSError as e:
                UI.err(f"cannot read {f}: {e}")
                return 1
        try:
            commit = hf.hf_upload(model, files, token, private=args.private)
        except RuntimeError as e:
            UI.err(f"HF push failed: {e}")
            return 1
        UI.ok(f"pushed {len(files)} file(s) to {model}")
        UI.info(f"commit: {commit.get('commitId', 'n/a')}")
        return 0
    UI.err("unknown hf subcommand")
    return 1


def cmd_token(args):
    meta = _load_meta()
    if meta is None:
        sys.exit("No token stored. Run `idun login` first.")
    expires_at = float(meta.get("expires_at", 0))
    remaining = int(expires_at - time.time())
    has_refresh = bool(meta.get("refresh_token"))
    UI.info(f"token len   : {len(meta.get('access_token', ''))}")
    UI.info(f"expires in  : {remaining}s ({'REFRESH PENDING' if remaining <= REFRESH_SLACK else 'ok'})")
    UI.info(f"refresh tok : {'yes' if has_refresh else 'no (device-code fallback)'}")
    if args.refresh or args.force:
        new = maybe_refresh(force=True)
        if new:
            UI.ok(f"refreshed -> len {len(new)}")
        else:
            UI.err("refresh returned no token")


def cmd_export(args):
    res = _run(args, args.prompt)
    payload = res.to_json() if args.fmt == "json" else res.to_markdown()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        UI.ok(f"wrote {args.fmt} trace -> {args.output} ({len(res.steps)} steps)")
    else:
        print(payload, file=sys.stderr)


def cmd_packs(_args):
    from idun import list_packs
    packs = list_packs()
    if not packs:
        UI.info("No prompt packs installed.")
        return
    UI.info("Available prompt packs:\n")
    for pk in packs:
        UI.info(f"  {pk['name']}  ({pk['count']} prompts) — {pk['title']}")
        if pk["description"]:
            UI.info(f"    {pk['description']}")


def cmd_matrix(args):
    """Build an N x M answer matrix from documents + questions (IDEA α)."""
    import json
    from idun.matrix import build_matrix
    from idun.ingest import load_documents
    docs = load_documents(args.docs)
    if not docs:
        UI.info("No .txt/.md/.pdf documents found in " + args.docs)
        return 1
    questions = [q.strip() for q in open(args.questions, encoding="utf-8") if q.strip()]
    if not questions:
        UI.info("No questions found in " + args.questions)
        return 1
    client = _client(args.backend)
    matrix = build_matrix(client, docs, questions)
    print(json.dumps(matrix, indent=2, ensure_ascii=False))
    return 0


def cmd_diff_docs(args):
    """Compare two documents across topics (IDEA γ: clause drift)."""
    import json
    from idun.matrix import build_drift
    from idun.ingest import extract_text
    try:
        a = extract_text(args.doc_a)
        b = extract_text(args.doc_b)
    except (ValueError, RuntimeError) as e:
        UI.info(str(e))
        return 1
    topics = [t.strip() for t in open(args.topics, encoding="utf-8") if t.strip()]
    if not topics:
        UI.info("No topics found in " + args.topics)
        return 1
    client = _client(args.backend)
    result = build_drift(client, a, b, topics)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_run(args):
    from idun import get_prompt, run_pack
    if args.all:
        if args.key:
            sys.exit("--all and KEY are mutually exclusive")
        results = run_pack(args.pack, keys=None, max_output_tokens=args.max_tokens)
        for key, res in results:
            if isinstance(res, Exception):
                UI.err(f"{key}: {res}")
                continue
            UI.chat_out(res.text, backend=args.pack)
        return
    if not args.key:
        sys.exit("either KEY or --all is required")
    try:
        prompt = get_prompt(args.pack, args.key)
    except (FileNotFoundError, KeyError) as e:
        sys.exit(str(e))
    res = _run(args, prompt)
    UI.chat_out(res.text, model=res.model,
                backend=getattr(args, "backend", None)
                or os.environ.get("IDUN_BACKEND")
                or os.environ.get("IDUN_PROVIDER") or "azure")


def cmd_diff(args):
    ra = _run(args, args.prompt_a)
    rb = _run(args, args.prompt_b)
    from idun import diff_traces, format_diff
    d = diff_traces(ra, rb)
    print(format_diff(d, args.fmt), file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="idun", description="NatureLM-Idun-5-MoE CLI (multi-backend)")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser(
        "login",
        help="store backend credentials",
        description=("Store credentials for a backend.\n\n"
                     "  idun login --backend azure    (device-code Entra login)\n"
                     "  idun login --backend hf       (Hugging Face token)\n"
                     "  idun login --backend openai   (OpenAI API key)"),
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
        help="show the Idun welcome (ASCII banner)",
        description="Render the Idun welcome screen (ASCII art banner).\n\nExample:\n  idun welcome",
    ).set_defaults(func=cmd_welcome)

    pw = sub.add_parser(
        "wizard",
        help="universal first-run setup for any user",
        description="Interactive setup for the Azure AI Foundry client (idun): endpoint / project / agent.\n\nExample:\n  idun wizard",
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
        description="Send a prompt and print only the final answer text.\n\nExample:\n  idun chat \"What is the capital of France?\"\n  idun chat --backend openai \"Summarize quantum computing\"\n  idun chat --async \"Explain transformers\"",
    )
    pc.add_argument("prompt", nargs="?", default="")
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
        description="Run a prompt and export the full agent trajectory to JSON or markdown.\n\nExample:\n  idun export \"What is the capital of France?\" -o trace.md\n  idun export --backend openai \"Explain photosynthesis\" -o trace.json\n  idun export --async \"Tell me a joke\" > out.md",
    )
    pe.add_argument("prompt")
    pe.add_argument("--format", choices=["json", "md"], default="json", dest="fmt",
                    help="json (full trajectory) or md (human-readable trace doc)")
    pe.add_argument("--output", "-o", help="write to file instead of stdout")
    _add_common_args(pe)
    pe.set_defaults(func=cmd_export)

    pm = sub.add_parser(
        "matrix", help="build Doc x Question answer matrix (IDEA α)")
    pm.add_argument("--docs", required=True, help="directory of .txt/.md documents")
    pm.add_argument("--questions", required=True, help="file with one question per line")
    pm.set_defaults(func=cmd_matrix)

    pd = sub.add_parser(
        "diff-docs", help="compare two documents across topics (IDEA γ: clause drift)")
    pd.add_argument("--doc-a", required=True, help="first document (.txt/.md/.pdf)")
    pd.add_argument("--doc-b", required=True, help="second document (.txt/.md/.pdf)")
    pd.add_argument("--topics", required=True, help="file with one topic per line")
    pd.set_defaults(func=cmd_diff_docs)

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



def cmd_wizard(_args):
    """`idun wizard` — first-run setup for the Azure AI Foundry client.

    Configures the Azure-specific settings (endpoint / project / agent) that
    `idun` (the Foundry client) needs, and writes them to ~/.idun/config.toml.
    Credentials are handled separately by `idun login --backend azure`.

    This is intentionally SEPARATE from `idun-multi wizard`, which configures
    the LLM providers. Both write only to config.toml (never ~/.idunrc), so
    there is no cross-file conflict — but they manage different sections.
    """
    if not sys.stdin.isatty():
        UI.err(
            "`idun wizard` needs an interactive TTY. Run it in a real terminal, "
            "or set credentials via `idun login --backend azure` / environment "
            "vars (IDUN_BASE, IDUN_PROJECT, IDUN_AGENT)."
        )
        return 1

    from idun import config as C

    UI.wizard_intro([
        "This sets up the Azure AI Foundry client (idun).",
        "1) azure  — point the SDK at YOUR Foundry resource",
        "s) skip   — keep current config",
        "q) quit   — exit without changing anything",
    ])

    def _read(prompt: str) -> str:
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return "q"

    choice = _read("Select [1, s=skip, q=quit]: ").lower()
    if choice in ("q", "quit", ""):
        UI.info("Wizard aborted — no changes made.")
        return 0
    if choice in ("s", "skip"):
        UI.info("Skipping Azure setup; keeping current config.")
        return 0

    cfg: dict = {"defaults": {}}
    base = _read("IDUN_BASE (https://<resource>.services.ai.azure.com): ")
    if base:
        cfg["azure"] = {"base": base}
        agent = _read("IDUN_AGENT (agent name) [optional]: ")
        if agent:
            cfg["azure"]["agent"] = agent
        project = _read("IDUN_PROJECT (Foundry project) [optional]: ")
        if project:
            cfg["azure"]["project"] = project
        UI.info("Run `idun login --backend azure` to complete the device-code flow.")
        C.write_config(cfg)
        UI.ok(f"wrote Azure config to {C.CONFIG_PATH}")
    else:
        UI.err("No base URL given — nothing to save.")
        return 1
    return 0


def main():
    maybe_welcome()
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

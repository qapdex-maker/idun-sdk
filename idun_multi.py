"""idun-multi: the 16-bit multi-provider console for the Idun SDK.

A provider-agnostic CLI built on :mod:`idun.providers` (registry + transports)
and :mod:`idun.retro` (16-colour ANSI chrome).

Commands:
    providers            list every provider with credential + model state
    login                store an API key for a provider (never echoed)
    ask PROMPT           send one prompt to the active/selected provider
    race PROMPT          fan the same prompt at several providers, compare
    models               show known model ids for a provider
    doctor               environment / credential / reachability check
    wizard               interactive 16-bit setup wizard
    banner               print the logo (sanity check for the retro layer)
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys

from idun import __version__ as VERSION
from idun import providers as P
from idun import retro as R

# VERSION is imported, never copied: a hardcoded literal here read "0.2.6" while
# the package was 1.0.22, so `idun-multi --version` and `idun-multi doctor` both
# reported a four-minor-old version. See tests/test_version_consistency.py.
RC_PATH = os.path.join(os.path.expanduser("~"), ".idunrc")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _active(args) -> str:
    flag = getattr(args, "provider", "") or P.default_provider()
    if flag and flag != "azure":
        return flag
    # respect a [defaults] provider = ... entry in ~/.idun/config.toml
    from idun import config as _cfg
    cfg_default = _cfg.config_default_provider()
    if cfg_default:
        return cfg_default
    return flag or "azure"


def _provider_rows() -> list[tuple]:
    rows = []
    for p in P.list_providers():
        cred = P.credential_status(p)
        icon = {"none": "-"}.get(cred, "+")
        rows.append((
            p.id,
            p.resolved_model(),
            "free" if p.free_tier else "paid",
            f"{icon} {cred}",
        ))
    return rows


def cmd_providers(args) -> int:
    print(R.logo(VERSION))
    print()
    print(R.box(
        R.table(_provider_rows(),
                headers=("provider", "model", "tier", "credential")).split("\n"),
        title=f"PROVIDERS  ({len(P.list_providers())})"))
    active = _active(args)
    print()
    print(R.status("info", "active provider: " + R.paint(active, "accent", "bold")))
    return 0


def cmd_models(args) -> int:
    try:
        p = P.get_provider(_active(args))
    except ValueError as e:
        print(R.status("err", str(e)))
        return 2
    lines = [f"base   : {p.resolved_base()}",
             f"default: {p.resolved_model()}",
             f"auth   : {P.credential_status(p)}"]
    if p.notes:
        lines.append(f"notes  : {p.notes}")
    lines.append("")
    if getattr(args, "discover", False):
        live = P.discover_models(p.id, force=True)
        lines.append(R.status("info", f"live models from GET {p.resolved_base().rstrip('/')}/models"))
    else:
        live = P.discover_models(p.id)
        if P._models_cache_get(p.id) is not None:
            lines.append(R.status("info", "showing cached discovery (use --discover to refresh)"))
    for m in live:
        mark = "*" if m == p.resolved_model() else " "
        lines.append(f" {mark} {m}")
    print(R.box(lines, title=f"{p.id.upper()} — {p.label}"))
    return 0


def cmd_login(args) -> int:
    try:
        p = P.get_provider(args.provider or _active(args))
    except ValueError as e:
        print(R.status("err", str(e)))
        return 2
    if not p.needs_key:
        print(R.status("ok", f"{p.id} needs no API key ({p.notes or 'local'})."))
        return 0
    import getpass
    prompt = f"{p.label} key ({p.env_key}): "
    token = getpass.getpass(prompt)
    if not token.strip():
        print(R.status("err", "empty key, aborted."))
        return 1
    path = P.save_credential(p, token)
    print(R.status("ok", f"stored credential -> {path} (0600)"))
    return 0


def _render_completion(c: P.Completion, *, raw: bool, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(c.to_dict(), ensure_ascii=False, indent=2))
        return
    if raw:
        print(c.text)
        return
    meta = (f"{c.provider} · {c.model} · {c.latency_ms} ms")
    if c.total_tokens:
        meta += f" · {c.total_tokens} tok"
    print(R.header("IDUN RESPONSE", meta))
    print()
    R.typewriter(c.text)
    print()
    if c.tool_calls:
        print(R.status("tool", "tool calls:"))
        for tc in c.tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "?")
            args = fn.get("arguments", "")
            print(f"  • {name}({args})")
        print()
    print(R.rule())


def _load_history(path: str) -> list[dict]:
    """Read a JSON conversation file into a list of {role, content} dicts.

    Accepts either a bare list of messages or an object with a ``messages``
    key (the shape ``idun-multi ask --save-history`` writes).
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("messages", [])
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list or {{'messages': [...]}}")
    return [m for m in data if isinstance(m, dict) and "role" in m and "content" in m]


def _save_history(path: str, history: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"messages": history}, fh, ensure_ascii=False, indent=2)


def cmd_ask(args) -> int:
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        print(R.status("err", "empty prompt."))
        return 2
    pid = _active(args)

    history = _load_history(args.resume) if args.resume else None
    if not args.raw and history is not None:
        print(R.status("info",
              f"resuming {R.paint(pid, 'accent')} · {len(history)} prior turns"))

    try:
        images = list(getattr(args, "image", []) or [])
        tools = None
        tools_arg = getattr(args, "tools", None)
        if tools_arg:
            import json as _json
            # accept a path or inline JSON
            if os.path.exists(tools_arg):
                with open(tools_arg, encoding="utf-8") as fh:
                    tools = _json.load(fh)
            else:
                tools = _json.loads(tools_arg)
        result = P.complete(pid, prompt, model=args.model, system=args.system or "",
                            temperature=args.temperature, max_tokens=args.max_tokens,
                            timeout=args.timeout, history=history,
                            stream=args.stream, images=images or None,
                            tools=tools,
                            tool_choice=getattr(args, "tool_choice", None))
    except (RuntimeError, ValueError) as e:
        print(R.status("err", str(e)))
        return 1

    # streaming returns a generator of text chunks; non-streaming a Completion
    if args.stream:
        chunks = result  # generator[str]
        if not args.raw and not getattr(args, "json", False):
            print(R.header("IDUN RESPONSE (stream)",
                           f"{pid} · {args.model or '(default)'}"))
            print()
        full = []
        try:
            for chunk in chunks:
                full.append(chunk)
                if args.raw:
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                # JSON mode: collect only; emit a single object at the end
                elif not getattr(args, "json", False):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
        except (RuntimeError, ValueError) as e:
            print(R.status("err", str(e)))
            return 1
        text = "".join(full)
        if getattr(args, "json", False):
            # streamed JSON: emit a completion-shaped object
            print(json.dumps({"provider": pid, "model": args.model or "",
                              "text": text, "streamed": True},
                             ensure_ascii=False, indent=2))
        elif not args.raw:
            print()
            print(R.rule())
    else:
        _render_completion(result, raw=args.raw, as_json=getattr(args, "json", False))
        text = result.text

    # build the cumulative transcript and optionally persist it
    if args.save_history or args.resume:
        transcript = list(history or [])
        transcript.append({"role": "user", "content": prompt})
        transcript.append({"role": "assistant", "content": text})
        out = args.save_history or args.resume
        _save_history(out, transcript)
        if not args.raw:
            print(R.status("info", f"history saved -> {out}"))
    return 0


def cmd_race(args) -> int:
    """Fan one prompt at several providers and compare latency + output."""
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        print(R.status("err", "empty prompt."))
        return 2
    if args.providers:
        pids = [x.strip() for x in args.providers.split(",") if x.strip()]
    else:
        # everything that currently holds a usable credential
        pids = [p.id for p in P.list_providers()
                if P.credential_status(p) not in ("none",)
                and p.transport != "azure"]
    if not pids:
        print(R.status("warn", "no providers with credentials. Run `idun-multi login`."))
        return 1

    print(R.header("PROVIDER RACE", f"{len(pids)} contenders · {prompt[:40]}"))
    results: dict[str, P.Completion | Exception] = {}

    def _one(pid: str) -> P.Completion | Exception:
        try:
            return P.complete(pid, prompt, max_tokens=args.max_tokens,
                              timeout=args.timeout)
        except (RuntimeError, ValueError) as e:
            return e

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(pids))) as ex:
        futs = {ex.submit(_one, pid): pid for pid in pids}
        for fut in concurrent.futures.as_completed(futs):
            results[futs[fut]] = fut.result()

    rows = []
    for pid in pids:
        res = results.get(pid)
        if isinstance(res, Exception):
            rows.append((pid, "-", "-", R.paint("FAILED", "err"), "-"))
        else:
            cost = P.estimate_cost(pid, res.prompt_tokens, res.completion_tokens)
            cost_s = f"${cost:.6f}" if cost is not None else "n/a"
            rows.append((pid, f"{res.latency_ms} ms",
                         str(res.total_tokens or "-"),
                         R.paint("ok", "ok"), cost_s))
    print()
    print(R.table(rows, headers=("provider", "latency", "tokens", "state", "cost*")))
    print()
    print(R.status("info",
                   "cost* = rough list-price estimate (USD); not a bill. "
                   "See `idun-multi cost` for the full table."))
    return 0


def cmd_cost(_args) -> int:
    """Print the approximate per-1K-token list-price table."""
    from idun.providers import cost_table
    print(R.header("IDUN COST TABLE", "approximate public list prices (USD / 1K tok)"))
    print()
    rows = []
    for pid, row in sorted(cost_table().items()):
        rows.append((pid, f"${row['in']:.5f}", f"${row['out']:.5f}"))
    print(R.table(rows, headers=("provider", "input/1K", "output/1K")))
    print()
    print(R.status("warn",
                   "Approximate list prices only — not a bill. Actual charges "
                   "depend on plan, region, caching, batch discounts. Self-hosted "
                   "(ollama/local), Azure Foundry (NatureLM-Idun) and HF Inference "
                   "have no public list price and are omitted."))
    return 0


def _shim_check() -> list[str]:
    """Verify that the `idun` console script really points at this package.

    Guards against failure F1: another project installing a script with the
    same name silently hijacks the command (the original symptom was
    `idun wizard` -> "no model found" from an unrelated llama.cpp launcher).
    """
    import shutil as _sh
    lines = []
    for name in ("idun", "idun-multi", "idun-mcp"):
        path = _sh.which(name)
        if not path:
            lines.append(R.status("warn", f"{name:10s} not on PATH"))
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                body = fh.read(2048)
        except OSError as e:
            lines.append(R.status("warn", f"{name:10s} unreadable: {e}"))
            continue
        expected = {"idun": "idun_cli", "idun-multi": "idun_multi",
                    "idun-mcp": "idun_mcp"}[name]
        if expected in body:
            lines.append(R.status("ok", f"{name:10s} -> {expected}"))
        else:
            import re as _re
            m = _re.search(r"from\s+(\S+)\s+import", body)
            hijacker = m.group(1) if m else "unknown"
            lines.append(R.status(
                "err", f"{name:10s} HIJACKED by {hijacker!r} — "
                       f"repair: pip install -e . --force-reinstall --no-deps"))
    return lines


def cmd_doctor(_args) -> int:
    print(R.header("IDUN DOCTOR", "environment + credential audit"))
    print()
    lines = [
        f"python      : {sys.version.split()[0]}",
        f"cli version : {VERSION}",
        f"config dir  : {P.CONFIG_DIR}"
        + (" (present)" if os.path.isdir(P.CONFIG_DIR) else " (missing)"),
        f"active      : {P.default_provider()}",
        f"rc file     : {RC_PATH}"
        + (" (present)" if os.path.exists(RC_PATH) else " (absent)"),
        f"colour      : {'on' if R.color_enabled() else 'off'}",
        f"theme       : {R.theme()}",
    ]
    # secret store: file (default) + optional OS keyring (opt-in)
    try:
        from idun.keyring_store import keyring_enabled
        kr = "keyring (opt-in)" if keyring_enabled() else "file only"
    except Exception:
        kr = "file only"
    lines.append(f"secrets     : {kr}")
    print(R.box(lines, title="ENVIRONMENT"))
    print()

    shim = _shim_check()
    broken = any("HIJACKED" in x for x in shim)
    print(R.box(shim, title="CONSOLE SCRIPTS"))
    print()

    ready = [p for p in P.list_providers() if P.credential_status(p) != "none"]
    missing = [p for p in P.list_providers() if P.credential_status(p) == "none"]
    print(R.box(
        [R.status("ok", f"{p.id:12s} {P.credential_status(p)}") for p in ready]
        or [R.paint("no provider configured", "warn")],
        title=f"READY ({len(ready)})"))
    print()
    if missing:
        print(R.box([R.status("warn", f"{p.id:12s} set {p.env_key or 'key'}")
                     for p in missing],
                    title=f"UNCONFIGURED ({len(missing)})"))
    print()
    print(R.status("ok" if ready else "warn",
                   f"{len(ready)}/{len(P.list_providers())} providers usable"))
    if broken:
        print(R.status("err", "console script hijacked — see CONSOLE SCRIPTS above"))
        return 2
    return 0 if ready else 1



def cmd_wizard(args) -> int:
    """`idun-multi wizard` — delegates to the unified idun-wizard (Teil D).

    The unified wizard (idun_cli.run_idun_wizard) is the single writer of
    first-run config: it writes only [defaults] provider to config.toml.
    This command no longer writes ~/.idunrc (the old conflict source).
    """
    from idun_cli import run_idun_wizard
    return run_idun_wizard(args)

def cmd_shell(args) -> int:
    """Interactive multi-turn REPL.

    Reads prompts from stdin (one per line), threads the running conversation
    through ``complete(history=...)``, and persists the full transcript to a
    JSON file when ``--save`` is given (the same format ``ask --resume``
    reads, so the two are interchangeable). Slash commands:

        /model <id>      switch model
        /provider <id>   switch provider
        /system <text>   set the system prompt
        /save [path]     persist the transcript now
        /clear           drop the in-memory history
        /quit            leave the shell
    """
    pid = _active(args)
    model = args.model or ""
    system = args.system or ""
    history: list[dict] = []
    save_path = args.save

    if args.resume:
        history = _load_history(args.resume)
        print(R.status("info",
              f"resumed {len(history)} turns from {args.resume}"))

    print(R.logo(VERSION))
    print(R.header("IDUN SHELL", f"{pid} · {model or 'default'}"))
    print(R.status("info",
          "type a prompt, or /help for commands. Ctrl-D exits."))
    print()

    while True:
        try:
            line = input(R.paint(f"{pid}> ", "accent", "bold")).rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.startswith("/"):
            cmd, _, rest = line[1:].partition(" ")
            rest = rest.strip()
            if cmd in ("quit", "exit"):
                break
            if cmd == "help":
                print(R.box([
                    "/model <id>      switch model",
                    "/provider <id>   switch provider",
                    "/system <text>   set system prompt",
                    "/save [path]     persist transcript",
                    "/clear           drop history",
                    "/quit            exit",
                ], title="SHELL COMMANDS"))
                continue
            if cmd == "model":
                model = rest
                print(R.status("ok", f"model -> {model or 'default'}"))
                continue
            if cmd == "provider":
                pid = rest or pid
                print(R.status("ok", f"provider -> {pid}"))
                continue
            if cmd == "system":
                system = rest
                print(R.status("ok", f"system -> {system or '(none)'}"))
                continue
            if cmd == "clear":
                history = []
                print(R.status("ok", "history cleared"))
                continue
            if cmd == "save":
                if rest:
                    save_path = rest
                if not save_path:
                    print(R.status("err", "no save path (use /save <file>)"))
                    continue
                _save_history(save_path, history)
                print(R.status("ok", f"saved -> {save_path}"))
                continue
            print(R.status("err", f"unknown command /{cmd}"))
            continue

        # normal prompt
        try:
            result = P.complete(pid, line, model=model, system=system,
                                history=history, stream=args.stream)
        except (RuntimeError, ValueError) as e:
            print(R.status("err", str(e)))
            continue

        if args.stream:
            full = []
            try:
                for chunk in result:
                    full.append(chunk)
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
            except (RuntimeError, ValueError) as e:
                print(R.status("err", str(e)))
                continue
            text = "".join(full)
            print()
        else:
            text = result.text
            _render_completion(result, raw=False, as_json=getattr(args, "json", False))

        history.append({"role": "user", "content": line})
        history.append({"role": "assistant", "content": text})
        if save_path:
            _save_history(save_path, history)

    if save_path and history:
        _save_history(save_path, history)
        print(R.status("info", f"session saved -> {save_path}"))
    return 0


def cmd_schema(args) -> int:
    """Print the response schema an Idun call returns (for JSON-mode clients)."""
    try:
        p = P.get_provider(_active(args))
    except ValueError as e:
        print(R.status("err", str(e)))
        return 2
    schema = {
        "provider": p.id,
        "model": p.resolved_model(),
        "transport": p.transport,
        "response": {
            "provider": "string",
            "model": "string",
            "text": "string",
            "prompt_tokens": "int",
            "completion_tokens": "int",
            "total_tokens": "int",
            "latency_ms": "int",
        },
        "json_mode_supported": p.transport in ("openai", "azure"),
        "notes": "Pass --json to `ask` to get exactly this shape per call.",
    }
    print(json.dumps(schema, ensure_ascii=False, indent=2))
    return 0


def cmd_support(_args) -> int:
    """Print the per-provider capability matrix (streaming / tools / vision /
    JSON mode). The flags are derived from the transports actually implemented
    in the SDK, so the table never drifts from the code.
    """
    from idun.providers import support_matrix_text
    print(R.header("IDUN SUPPORT MATRIX", "per-provider capabilities"))
    print()
    print(support_matrix_text())
    print()
    print(R.paint("streaming: true SSE (openai); azure = single chunk via agent "
                  "client; anthropic/hf = single-chunk fallback", "dim"))
    print(R.paint("tools: agent tool-trace surfaced (azure tool-agent only)", "dim"))
    print(R.paint("vision: not wired into complete() for any provider yet", "dim"))
    print(R.paint("json_mode: response_format accepted by openai + azure transports",
                  "dim"))
    return 0


def cmd_theme(args) -> int:
    """Show or switch the active retro theme (classic/c64/gameboy/amiga/cga)."""
    if getattr(args, "name", ""):
        active = R.set_theme(args.name)
        print(R.status("ok", f"theme -> {active}"))
    else:
        active = R.theme()
    rows = [(tid, R.paint("active", "ok") if tid == active else "")
            for tid in R.list_themes()]
    print(R.box(
        R.table(rows, headers=("theme", "state")).split("\n"),
        title="RETRO THEMES  (set IDUN_THEME or `idun-multi theme <name>`)"))
    return 0


def cmd_banner(_args) -> int:
    print(R.logo(VERSION))
    print()
    print(R.box(["16-colour ANSI chrome self-test",
                 R.status("ok", "status ok"),
                 R.status("warn", "status warn"),
                 R.status("err", "status err"),
                 R.bar(0.25), R.bar(0.6), R.bar(1.0)],
                title="RETRO SELF-TEST"))
    return 0


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="idun-multi",
        description="16-bit multi-provider LLM console (Idun SDK).")
    ap.add_argument("--version", action="version", version=f"idun-multi {VERSION}")
    ap.add_argument("-p", "--provider", default="",
                    help="provider id (default: $IDUN_PROVIDER or azure)")
    sub = ap.add_subparsers(dest="cmd")

    sp = sub.add_parser("providers", help="list all providers and credentials")
    sp.set_defaults(func=cmd_providers)

    sp = sub.add_parser("models", help="show models for a provider")
    sp.add_argument("--discover", action="store_true",
                    help="fetch live model list from GET {base}/models (cached 24h)")
    sp.set_defaults(func=cmd_models)

    sp = sub.add_parser("login", help="store an API key for a provider")
    sp.add_argument("--provider", default="")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("ask", help="send one prompt")
    sp.add_argument("prompt", nargs="+")
    sp.add_argument("--model", default="")
    sp.add_argument("--system", default="",
                    help="system prompt (prepended to the conversation)")
    sp.add_argument("--resume", default="",
                    help="resume a saved conversation from this JSON file")
    sp.add_argument("--save-history", default="",
                    help="after answering, append this turn and write the "
                         "full transcript to this JSON file")
    sp.add_argument("--temperature", type=float, default=0.7)
    sp.add_argument("--max-tokens", type=int, default=1024, dest="max_tokens")
    sp.add_argument("--timeout", type=int, default=120)
    sp.add_argument("--stream", action="store_true",
                    help="stream tokens as they arrive (openai transport)")
    sp.add_argument("--raw", action="store_true", help="plain text, no chrome")
    sp.add_argument("--json", action="store_true",
                    help="emit the Completion as JSON (for scripting)")
    sp.add_argument("--image", action="append", default=[],
                    help="image ref for vision: http(s) URL, data: URI, or local "
                         "path. Repeatable. (openai/anthropic transports)")
    sp.add_argument("--tools", default=None,
                    help="function-calling tool schemas: inline JSON or a path to "
                         "a JSON file (list of OpenAI-style tool defs). "
                         "(openai/anthropic transports)")
    sp.add_argument("--tool-choice", default=None,
                    help="tool selector: 'auto' (default), 'none', or "
                         "{\"type\":\"function\",\"function\":{\"name\":\"...\"}}")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("shell", help="interactive multi-turn REPL")
    sp.add_argument("--model", default="")
    sp.add_argument("--system", default="",
                    help="system prompt for the whole session")
    sp.add_argument("--resume", default="",
                    help="start the shell from a saved transcript JSON")
    sp.add_argument("--save", default="",
                    help="persist the session transcript to this JSON file")
    sp.add_argument("--stream", action="store_true",
                    help="stream tokens as they arrive (openai transport)")
    sp.add_argument("--timeout", type=int, default=120)
    sp.add_argument("--json", action="store_true",
                    help="emit each turn as JSON (for scripting)")
    sp.set_defaults(func=cmd_shell)

    sp = sub.add_parser("race", help="compare providers on one prompt")
    sp.add_argument("prompt", nargs="+")
    sp.add_argument("--providers", default="", help="comma list (default: all ready)")
    sp.add_argument("--lines", type=int, default=6, help="preview lines per answer")
    sp.add_argument("--max-tokens", type=int, default=512, dest="max_tokens")
    sp.add_argument("--timeout", type=int, default=120)
    sp.set_defaults(func=cmd_race)

    sp = sub.add_parser("cost", help="show the approximate list-price table")
    sp.set_defaults(func=cmd_cost)

    sp = sub.add_parser("doctor", help="environment and credential audit")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("schema", help="show the JSON response schema")
    sp.set_defaults(func=cmd_schema)

    sp = sub.add_parser("support", help="show the per-provider capability matrix")
    sp.set_defaults(func=cmd_support)

    sp = sub.add_parser("theme", help="show or switch the retro theme")
    sp.add_argument("name", nargs="?", default="",
                    help="theme id: classic|c64|gameboy|amiga|cga")
    sp.set_defaults(func=cmd_theme)

    sp = sub.add_parser("wizard", help="interactive setup")
    sp.set_defaults(func=cmd_wizard)

    sp = sub.add_parser("banner", help="print the logo / retro self-test")
    sp.set_defaults(func=cmd_banner)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        print(R.logo(VERSION))
        print()
        ap.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print()
        print(R.status("warn", "interrupted."))
        return 130


if __name__ == "__main__":
    sys.exit(main())

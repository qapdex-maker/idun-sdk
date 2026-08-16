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
import os
import sys

from idun import providers as P
from idun import retro as R

VERSION = "0.2.1"
RC_PATH = os.path.join(os.path.expanduser("~"), ".idunrc")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _active(args) -> str:
    return (getattr(args, "provider", "") or P.default_provider())


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
    for m in (p.models or (p.default_model,)):
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
    token = args.token or getpass.getpass(prompt)
    if not token.strip():
        print(R.status("err", "empty key, aborted."))
        return 1
    path = P.save_credential(p, token)
    print(R.status("ok", f"stored credential -> {path} (0600)"))
    return 0


def _render_completion(c: P.Completion, *, raw: bool) -> None:
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
    print(R.rule())


def cmd_ask(args) -> int:
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        print(R.status("err", "empty prompt."))
        return 2
    pid = _active(args)
    if not args.raw:
        print(R.status("info", f"asking {R.paint(pid, 'accent')} ..."))
    try:
        c = P.complete(pid, prompt, model=args.model, system=args.system or "",
                       temperature=args.temperature, max_tokens=args.max_tokens,
                       timeout=args.timeout)
    except (RuntimeError, ValueError) as e:
        print(R.status("err", str(e)))
        return 1
    _render_completion(c, raw=args.raw)
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
            rows.append((pid, "-", "-", R.paint("FAILED", "err")))
        else:
            rows.append((pid, f"{res.latency_ms} ms",
                         str(res.total_tokens or "-"),
                         R.paint("ok", "ok")))
    print()
    print(R.table(rows, headers=("provider", "latency", "tokens", "state")))
    print()

    for pid in pids:
        res = results.get(pid)
        if isinstance(res, Exception):
            msg = " ".join(str(res).split())
            print(R.box([msg[:160]], title=f"{pid} — ERROR", role="err"))
        else:
            body = res.text.strip().split("\n")[: args.lines] or ["(empty)"]
            print(R.box(body, title=f"{pid} — {res.model} ({res.latency_ms} ms)"))
        print()
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
    ]
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
    """Interactive setup. Non-interactive stdin degrades gracefully."""
    print(R.logo(VERSION))
    print()
    provs = list(P.list_providers())
    rows = [(str(i + 1), p.id, p.label, "free" if p.free_tier else "paid")
            for i, p in enumerate(provs)]
    print(R.box(R.table(rows, headers=("#", "id", "provider", "tier")).split("\n"),
                title="SELECT A PROVIDER"))
    print()

    if not sys.stdin.isatty():
        print(R.status("warn", "stdin is not a TTY — wizard needs an interactive "
                               "shell."))
        print(R.status("info", "non-interactive alternative:"))
        print("    idun-multi login --provider groq --token <KEY>")
        print("    export IDUN_PROVIDER=groq")
        return 1

    try:
        choice = input(R.paint("  select [1-%d]: " % len(provs), "accent")).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print(R.status("warn", "aborted."))
        return 1
    if not choice.isdigit() or not 1 <= int(choice) <= len(provs):
        print(R.status("err", "invalid selection."))
        return 2
    p = provs[int(choice) - 1]
    print(R.status("ok", f"selected {R.paint(p.id, 'accent', 'bold')}"))

    if p.needs_key and P.credential_status(p) == "none":
        import getpass
        try:
            tok = getpass.getpass(f"  {p.env_key}: ").strip()
        except (EOFError, KeyboardInterrupt):
            tok = ""
        if tok:
            P.save_credential(p, tok)
            print(R.status("ok", "credential stored (0600)."))
        else:
            print(R.status("warn", "no key stored — set it later via login."))

    model = ""
    try:
        model = input(f"  model [{p.resolved_model()}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        pass

    cfg = {"IDUN_PROVIDER": p.id}
    if model:
        cfg[p.model_env()] = model
    with open(RC_PATH, "a", encoding="utf-8") as fh:
        fh.write("\n# idun-multi wizard\n")
        for k, v in cfg.items():
            fh.write(f"export {k}={v}\n")
    os.chmod(RC_PATH, 0o600)

    print()
    print(R.box([f"wrote {RC_PATH}",
                 "source ~/.idunrc   # activate in this shell",
                 f"idun-multi ask \"hello\"   # talk to {p.id}"],
                title="NEXT STEPS"))
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
    sp.set_defaults(func=cmd_models)

    sp = sub.add_parser("login", help="store an API key for a provider")
    sp.add_argument("--provider", default="")
    sp.add_argument("--token", default="", help="key (omit for a hidden prompt)")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("ask", help="send one prompt")
    sp.add_argument("prompt", nargs="+")
    sp.add_argument("--model", default="")
    sp.add_argument("--system", default="")
    sp.add_argument("--temperature", type=float, default=0.7)
    sp.add_argument("--max-tokens", type=int, default=1024, dest="max_tokens")
    sp.add_argument("--timeout", type=int, default=120)
    sp.add_argument("--raw", action="store_true", help="plain text, no chrome")
    sp.set_defaults(func=cmd_ask)

    sp = sub.add_parser("race", help="compare providers on one prompt")
    sp.add_argument("prompt", nargs="+")
    sp.add_argument("--providers", default="", help="comma list (default: all ready)")
    sp.add_argument("--lines", type=int, default=6, help="preview lines per answer")
    sp.add_argument("--max-tokens", type=int, default=512, dest="max_tokens")
    sp.add_argument("--timeout", type=int, default=120)
    sp.set_defaults(func=cmd_race)

    sp = sub.add_parser("doctor", help="environment and credential audit")
    sp.set_defaults(func=cmd_doctor)

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

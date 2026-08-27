"""idun-multi: the 16-bit multi-provider console for the Idun SDK.

A provider-agnostic CLI built on :mod:`idun.providers` (registry + transports)
and :mod:`idun.retro` (16-colour ANSI chrome).

Commands:
    providers            list every provider with credential + model state
    login                store an API key for a provider (never echoed)
    ask PROMPT           send one prompt to the active/selected provider
    race PROMPT          fan the same prompt at several providers, compare
    verify               live smoke-test configured providers (writes log)
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
from idun import _cli_retro as UI
from idun import verification as V

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
        live = V.state(pid)
        live_cell = _verify_mark_cli(live.state)
        if isinstance(res, Exception):
            rows.append((pid, "—", "—", R.paint("FAILED", "err"), "—", live_cell))
            # a real failure during a race is a failed live check
            if not (P.credential_status(P.get_provider(pid)) == "none" and
                    P.get_provider(pid).needs_key):
                V.record(pid, V.VerifyRecord(
                    state=V.FAIL,
                    error=P._sanitize_error_body(str(res))[:200],
                    ts=__import__("time").time()))
        else:
            cost = P.estimate_cost(pid, res.prompt_tokens, res.completion_tokens)
            cost_s = f"${cost:.6f}" if cost is not None else "n/a"
            from typing import cast
            comp = cast("P.Completion", res)
            rows.append((pid, f"{comp.latency_ms} ms",
                         str(comp.total_tokens or "—"),
                         R.paint("ok", "ok"), cost_s, live_cell))
            # a successful race leg is a successful live check
            V.record(pid, V.VerifyRecord(
                state=V.OK, model=comp.model,
                ts=__import__("time").time(), latency_ms=comp.latency_ms))
    print()
    print(R.table(rows, headers=("provider", "latency", "tokens", "state",
                                 "cost*", "live")))
    print()
    print(R.status("info",
                   "cost* = rough list-price estimate (USD); not a bill. "
                   "See `idun-multi cost` for the full table.\n"
                   "live = last recorded verification state "
                   "(✓ live / ✗ fail / ⊘ skip / ? unverified)."))
    return 0


def _verify_state_mark(rec: "V.VerifyRecord") -> str:
    return {
        V.OK: R.paint("ok", "ok"),
        V.FAIL: R.paint("FAIL", "err"),
        V.SKIPPED: R.paint("skip", "warn"),
        V.UNKNOWN: R.paint("?", "dim"),
    }.get(rec.state, R.paint("?", "dim"))


def _verify_mark_cli(state_str: str) -> str:
    return {
        V.OK: R.paint("✓ live", "ok"),
        V.FAIL: R.paint("✗ fail", "err"),
        V.SKIPPED: R.paint("⊘ skip", "warn"),
        V.UNKNOWN: R.paint("? unverified", "dim"),
    }.get(state_str, R.paint("? unverified", "dim"))


def cmd_verify(args) -> int:
    """Live smoke-test every configured provider and record the result.

    Offline-safe: unconfigured providers are reported as ``skip`` (not
    ``fail``). Requires network access for the actual calls; there is no mock
    path. Results persist in ``~/.idun/.verified.json`` and feed the ``live``
    column of `support` / `race`.
    """
    if args.providers:
        ids = [x.strip() for x in args.providers.split(",") if x.strip()]
        chosen = []
        for pid in ids:
            try:
                chosen.append(P.get_provider(pid))
            except ValueError as e:
                print(R.status("err", str(e)))
                return 2
    else:
        chosen = list(P.list_providers())

    print(R.header("PROVIDER VERIFY",
                   f"{len(chosen)} providers · live API smoke test"))
    print(R.status("info",
                   "unconfigured providers are skipped, not failed. "
                   "needs network; no mock path."))
    print()

    def _on(pid, rec):
        mark = _verify_state_mark(rec)
        extra = ""
        if rec.state == V.OK and rec.latency_ms is not None:
            extra = f"{rec.latency_ms} ms · {rec.model}"
        elif rec.state == V.FAIL and rec.error:
            extra = rec.error
        elif rec.state == V.SKIPPED:
            extra = rec.error or ""
        print(f"  {pid:12s} {mark}  {extra}")

    results = V.run_checks(chosen, max_tokens=args.max_tokens,
                           timeout=args.timeout, on_result=_on)
    print()
    ok = sum(1 for r in results.values() if r.state == V.OK)
    skip = sum(1 for r in results.values() if r.state == V.SKIPPED)
    fail = sum(1 for r in results.values() if r.state == V.FAIL)
    print(R.status("ok" if fail == 0 else "warn",
                   f"verify done: {ok} ok · {fail} fail · {skip} skipped "
                   f"of {len(results)}"))
    # Persist is handled inside run_checks; just save a fresh SUPPORT_MATRIX.
    _regenerate_support_md()
    return 0 if fail == 0 else 1


def _regenerate_support_md() -> None:
    """Re-render SUPPORT_MATRIX.md from the (now updated) support matrix.

    Best-effort: if the file isn't where we expect, skip silently — the CLI
    `support` command is the source of truth anyway.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        # idun_multi.py lives at the repo root, so SUPPORT_MATRIX.md is beside
        # it (not one directory up, as it would be for modules under idun/).
        cand = os.path.join(here, "SUPPORT_MATRIX.md")
        if not os.path.isfile(cand):
            return
        body = P.support_matrix_text()
        pre = ("# Idun SDK - Support Matrix\n\n"
               "Per-provider capability matrix. **Generated from the transports "
               "actually implemented in `idun/providers.py`** (via "
               "`idun.providers.support_matrix()`), so this never drifts from "
               "the code. Re-render with `idun-multi support`.\n\n")
        post = (
            "\n\n## What the columns mean\n\n"
            "- **Streaming** - true SSE token streaming (`openai` transport). "
            "Azure answers in a single chunk via the agent client; "
            "`anthropic`/`hf` fall back to a single-chunk yield so callers "
            "can still iterate.\n"
            "- **Tools** - function calling wired through "
            "`complete(tools=[...])` for the `openai` + `anthropic` transports. "
            "Tool calls are returned on `Completion.tool_calls` (normalized to "
            "OpenAI shape). The Azure Foundry agent tool-trace is surfaced "
            "separately via `IdunClient` (the `idun` CLI), not via `complete()`.\n"
            "- **Vision** - multimodal input wired through "
            "`complete(images=[...])` for the `openai` + `anthropic` transports "
            "(image_url / image content blocks; local files are "
            "base64-encoded). `hf` and the Azure `complete()` path are "
            "text-only.\n"
            "- **JSON mode** - `response_format` / structured output accepted. "
            "Follows the same rule as `idun-multi schema` (`openai` + `azure` "
            "transports). Use `--json` on any command for the normalized shape.\n"
            "- **Declared** - the registry maintainer has smoke-tested this "
            "provider at least once and recorded it as working.\n"
            "- **Live** - result of the most recent actual API call from this "
            "machine (`idun-multi verify` / `race`). `✓ live` = last call "
            "succeeded, `✗ fail` = last call errored, `⊘ skip` = no credential "
            "configured, `?` = never called from this install.\n\n"
            "## Any OpenAI-compatible endpoint\n\n"
            "Providers using the `openai` transport (groq, openrouter, together, "
            "deepseek, mistral, gemini, xai, nous, ollama, local, perplexity, "
            "fireworks, novita) inherit the `openai` transport's capabilities: "
            "**streaming YES, tools YES, vision YES, JSON mode YES**. The "
            "wizard option `5) other` and `IDUN_<ID>_BASE` let you point any "
            "OpenAI-compatible endpoint at the same transport with zero code "
            "changes.\n\n"
            "## Using vision + tools from the CLI\n\n"
            "```bash\n"
            "idun-multi ask \"What is in this chart?\" --image ./chart.png\n"
            "idun-multi ask \"Get the weather\" \\\n"
            "  --tools '{\"type\":\"function\",\"function\":{\"name\":\"get_weather\","
            "\\\"description\\\":\\\"weather\\\",\\\"parameters\\\":{\\\"type\\\":"
            "\\\"object\\\",\\\"properties\\\":{\\\"city\\\":{\\\"type\\\":\\\"string\\\"}}}}}'\n"
            "idun-multi ask \"Get the weather\" --tools ./tools.json   # JSON file\n"
            "```\n\n"
            "From Python:\n\n"
            "```python\n"
            "from idun.providers import complete\n"
            "c = complete(\"groq\", \"weather?\", images=[\"https://x/cat.png\"],\n"
            "             tools=[{\"type\": \"function\", \"function\": {\n"
            "                 \"name\": \"get_weather\", \"parameters\": {\n"
            "                 \"type\": \"object\", \"properties\": "
            "{\"city\": {\"type\": \"string\"}}}}}]\n"
            "print(c.text, c.tool_calls)\n"
            "```\n"
        )
        with open(cand, "w", encoding="utf-8") as fh:
            fh.write(pre + body + post)
    except OSError:
        pass


def _review_providers() -> list[str]:
    """Provider mit Credential, die zum Review genutzt werden (Ensemble)."""
    wanted = ["anthropic", "hf", "deepseek", "openai", "gemini", "mistral"]
    pids = []
    for pid in wanted:
        p = P.get_provider(pid)
        if p and P.credential_status(p) not in ("none",):
            pids.append(pid)
    # fallback: alle mit credential
    if not pids:
        pids = [p.id for p in P.list_providers()
                if P.credential_status(p) not in ("none",) and p.transport != "azure"]
    return pids[:3]  # max 3 contenders


def cmd_review(args) -> int:
    """Self-built PR reviewer: diff -> race over providers -> post PR comment.

    MVP (ROADMAP Open #4, self-built decision 2026-08-27). Uses idun-multi's
    existing LLM engine + providers; posts a merged review as a PR comment.
    Complements `cmd_verify` (which smoke-tests provider connectivity) — this
    reviews a GitHub PR, it does not touch provider verification.
    """
    import subprocess

    pr = args.pr
    repo = args.repo or "qapdex-maker/idun-sdk"
    # pr kann "#123", "123", "owner/repo#123" oder "https://.../pull/123" sein
    gh_repo = repo
    gh_pr = pr
    if "#" in pr and "/" in pr:
        gh_repo, _, num = pr.partition("#")
        gh_pr = num
    elif pr.startswith("http"):
        # https://github.com/owner/repo/pull/123
        import re
        m = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", pr)
        if m:
            gh_repo, gh_pr = m.group(1), m.group(2)
    elif pr.isdigit() or (pr.startswith("#") and pr[1:].isdigit()):
        gh_pr = pr.lstrip("#")

    print(R.header("IDUN REVIEW", f"{gh_repo}#{gh_pr}"))
    # 1) diff holen
    try:
        diff = subprocess.run(
            ["gh", "pr", "diff", gh_pr, "--repo", gh_repo],
            capture_output=True, text=True, timeout=120
        ).stdout
    except FileNotFoundError:
        print(R.status("err", "gh CLI nicht gefunden."))
        return 1
    if not diff.strip():
        print(R.status("warn", "leerer diff — PR nicht gefunden oder kein Zugriff."))
        return 1
    print(R.status("info", f"diff: {len(diff)} bytes"))

    # 2) diff in chunks splitten (Modell-Kontext)
    max_chunk = 6000
    chunks = [diff[i:i + max_chunk] for i in range(0, len(diff), max_chunk)] or [diff]
    print(R.status("info", f"{len(chunks)} chunk(s) zum Review"))

    pids = _review_providers()
    if not pids:
        print(R.status("err", "keine Provider mit Credential. `idun-multi login`."))
        return 1
    print(R.status("info", f"Ensemble: {', '.join(pids)}"))

    review_prompt = (
        "Du bist ein strenger Code-Reviewer. Finde nur echte Probleme: Bugs, "
        "Security-Issues (Token-Leaks, Path-Traversal), Crashes, Dead-Code, "
        "Regressionen. Ignoriere Style. Antworte kompakt, eine Zeile pro Fund, "
        "mit Datei:Zeile falls erkennbar. Wenn sauber: 'KEINE FUNDE'."
    )

    comments = []
    for idx, chunk in enumerate(chunks, 1):
        full = f"{review_prompt}\n\n--- DIFF CHUNK {idx}/{len(chunks)} ---\n{chunk}"
        lines = []
        for pid in pids:
            try:
                res = P.complete(pid, full, max_tokens=600, timeout=150)
                from typing import cast
                res = cast("P.Completion", res)
                lines.append(f"[{pid}] {res.text.strip()}")
            except (RuntimeError, ValueError) as e:
                lines.append(f"[{pid}] ERROR: {e}")
        comments.append("\n".join(lines))

    body = "## 🤖 idun-multi self-built review\n\n" + "\n\n---\n\n".join(comments)
    print()
    print(R.header("REVIEW (lokal)", f"{len(comments)} chunk(s)"))
    print(body[:2000])

    # 3) als PR-Comment posten
    if args.post:
        try:
            subprocess.run(["gh", "pr", "comment", gh_pr, "--repo", gh_repo,
                            "--body", body], check=True, timeout=60)
            print(R.status("ok", "als PR-Comment gepostet."))
        except subprocess.CalledProcessError as e:
            print(R.status("err", f"Post fehlgeschlagen: {e}"))
            return 1
    else:
        print(R.status("info", "Trockenlauf (--post zum Veröffentlichen)."))
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
        # NOTE: .idunrc is no longer written by any wizard (it caused the
        # config conflict). Kept as an informational line only if it exists.
        (f"rc file     : {RC_PATH} (present)" if os.path.exists(RC_PATH)
         else "rc file     : ~/.idunrc (absent — no longer used)"),
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
    """`idun-multi wizard` — first-run setup for the LLM providers.

    Lets the user pick one of the 17 registered providers (registry-driven),
    optionally stores its credential via getpass, and writes
    `[defaults] provider = <id>` to ~/.idun/config.toml. This is the ONLY
    writer of the provider default for idun-multi.

    Intentionally SEPARATE from `idun wizard`, which configures the Azure
    Foundry client. Both write only to config.toml (never ~/.idunrc), so there
    is no cross-file conflict — but they manage different sections.
    """
    if not sys.stdin.isatty():
        UI.err(
            "`idun-multi wizard` needs an interactive TTY. Run it in a real "
            "terminal, or set the provider via `idun-multi login --provider X` "
            "/ environment vars (IDUN_PROVIDER)."
        )
        return 1

    from idun import config as C
    from idun.providers import REGISTRY, save_credential, credential_status

    provs = list(REGISTRY)
    # Build and PRINT the provider table so the user can actually choose.
    rows = [(str(i + 1), p.id, p.label, "free" if p.free_tier else "paid")
            for i, p in enumerate(provs)]
    UI.wizard_intro([
        "This sets up the multi-provider LLM console (idun-multi).",
    ])
    try:
        print(R.table(rows, headers=("n", "provider-id", "name", "tier")))
    except Exception:
        # fallback: plain listing
        for n, pid, label, tier in rows:
            print(f"  {n}) {pid:12} {label} ({tier})")
    print("  s) skip — keep current default")
    print("  q) quit — exit without changing anything")

    def _read(prompt: str) -> str:
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return "q"

    choice = _read(f"Select provider [1-{len(provs)}, s=skip, q=quit]: ").lower()
    if choice in ("q", "quit", ""):
        UI.info("Wizard aborted — no changes made.")
        return 0
    if choice in ("s", "skip"):
        UI.info("Skipping provider setup; keeping current default.")
        return 0

    try:
        idx = int(choice) - 1
        if not 0 <= idx < len(provs):
            raise ValueError
    except ValueError:
        UI.err("Invalid selection.")
        return 2

    p = provs[idx]
    UI.info(f"selected {p.id}")

    if p.needs_key and credential_status(p) == "none":
        import getpass
        try:
            tok = getpass.getpass(f"  {p.env_key}: ").strip()
        except (EOFError, KeyboardInterrupt):
            tok = ""
        if tok:
            save_credential(p, tok)
            UI.ok("credential stored (0600).")
        else:
            UI.info("no key stored — set it later via `idun-multi login`.")

    C.write_config({"defaults": {"provider": p.id}})
    UI.ok(f"wrote default provider '{p.id}' to {C.CONFIG_PATH}")
    return 0

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
    JSON mode / declared / live). The capability flags are derived from the
    transports actually implemented in the SDK, so the table never drifts from
    the code. ``live`` is the result of the most recent actual API call from
    this machine (`idun-multi verify` / `race`); `?` means never called here.
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
    print(R.paint("declared: registry maintainer smoke-tested this provider",
                  "dim"))
    print(R.paint("live: ✓ live=last call ok · ✗ fail=last call errored · "
                  "⊘ skip=no credential · ?=never called here", "dim"))
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

    sp = sub.add_parser("verify",
                        help="live smoke-test configured providers (writes "
                             "~/.idun/.verified.json)")
    sp.add_argument("--providers", default="",
                    help="comma list (default: all providers)")
    sp.add_argument("--max-tokens", type=int, default=8, dest="max_tokens")
    sp.add_argument("--timeout", type=int, default=30)
    sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("review",
                        help="self-built PR reviewer (diff -> race -> comment)")
    sp.add_argument("pr", help="#123 | 123 | owner/repo#123 | https://.../pull/123")
    sp.add_argument("--repo", default="", help="owner/repo (default qapdex-maker/idun-sdk)")
    sp.add_argument("--post", action="store_true",
                    help="post the merged review as a PR comment (default: dry-run)")
    sp.set_defaults(func=cmd_review)

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

# Idun SDK — Rework Roadmap (v0.2.0 → v1.0)

Status of this document: ACTIVE. All planned v0.4 / v0.5 / v1.0 items are
implemented and verified (SDK at **v1.0.0**). A small post-v1.0 maintenance
track (v1.0.1 … v1.0.6) captured follow-up fixes that shipped after the
original "FINAL" sign-off. The backlog in §8 is still future work.

---

## 1. Audit findings (what was actually broken)

(Unchanged from the v0.2.0 audit — see git history. F1–F6 were all resolved
by v0.2.7; the registry, retro UI, CLI, and test suite established there are
what the v0.4–v1.0 features build on.)

---

## 2. Done in v0.2.0 (implemented + verified)

(See git history / previous roadmap revision. Provider registry, 16-bit retro
UI, `idun-multi` CLI, and 74 offline tests were shipped and verified live.)

---

## 2b. Shipped since v0.2.0 (v0.2.1 → v0.2.7)

(See git history / previous roadmap revision. v0.2.1 tenant removal, v0.2.2
security remediation, v0.2.3 backend resolution, v0.2.4 unified retro UI,
v0.2.5 Nous + resume, v0.2.6 streaming + REPL, v0.2.7 retire backends.py.)

---

## 3. v0.3 — DONE

1. **Streaming** (`--stream`) — DONE in v0.2.6.
2. **Interactive REPL** (`idun-multi shell`) — DONE in v0.2.6.
3. **Retire `backends.py`** — DONE in v0.2.7.
4. **Console-script collision guard** — DONE in v0.2.0 (doctor check).
5. **Cost accounting** — *deferred*: not in scope for v1.0. The `race` command
   reports latency + token counts; a price table would be a registry-only
   addition later. (No provider-agnostic public price API; left for a follow-up.)
6. **Provider expansion** — Nous Research added in v0.2.5. v1.0 ships 14
   providers (incl. Nous); new OpenAI-compatible endpoints are one `Provider(...)` row.

---

## 4. v0.4 — DONE

6. **Fallback chains** — DONE. `complete_chain(chain, prompt)` walks
   `IDUN_CHAIN` (or an explicit list), skipping retryable/auth/transport
   failures, recording the winning link in `raw["_served_by"]` and the skipped
   links in `raw["_chain"]`. Tests: `tests/test_chain.py`.
7. **Response caching** — DONE in v0.2.7 (`~/.idun/cache`, `IDUN_NO_CACHE=1`).
8. **Retry with backoff** — DONE in v0.2.7 (honors `Retry-After`, jitter, cap).
9. **Config file** — DONE. `idun/config.py` (stdlib-only TOML reader) makes
   `~/.idun/config.toml` the primary source. Resolution: **env > config.toml >
   registry default**. A corrupt file never crashes startup. Tests:
   `tests/test_config.py`.
10. **Structured output** — DONE. Every completion command supports `--json`
    (single completion-shaped object at the end; streaming still prints live),
    and `schema` shows the per-provider response schema incl. `json_mode`
    support. `Completion.to_dict()` / `from_dict()` added. Tests:
    `tests/test_structured_output.py`.

---

## 5. v0.5 — DONE

11. **MCP server parity** — DONE. `idun_mcp.py` now exposes `idun_providers`
    (registry + credential state), `idun_ask` (any provider via
    `providers.complete`), and `idun_race` (fan + latency/state) alongside the
    original `idun_chat` / `idun_trace` / `idun_export` / `idun_token` tools.
    Verified against the JSON-RPC wire contract offline. Tests:
    `tests/test_mcp_parity.py`.
12. **Async client** — DONE. `idun/async_client.py` `AsyncIdunClient` with
    `acomplete()` / `acomplete_chain()` running the stdlib urllib transport via
    `asyncio.to_thread` (no dedicated pool) + a `gather()` helper for fan-out.
    Tests: `tests/test_async_client.py`.
13. **Model discovery** — DONE. `discover_models(pid)` fetches
    `GET {base}/models` for openai/azure transports, caches under
    `~/.idun/models/<id>.json` (24h; `IDUN_NO_MODELS_CACHE` /
    `IDUN_MODELS_CACHE_MAX_AGE`), falls back to registry models on error or
    non-OpenAI transport. `_require_http_url` rejects `file://` etc. `idun-multi
    models --discover` forces a refresh. Tests: `tests/test_model_discovery.py`.
14. **Theme system** — DONE. Selectable palettes `classic` / `c64` / `gameboy`
    / `amiga` / `cga` via `IDUN_THEME` (applied at import) or the `theme`
    command; `doctor` reports the active theme. Unknown ids fall back to
    `classic`. Tests: `tests/test_theme.py`.

---

## 6. v1.0 — DONE

15. **CI matrix** — DONE. `.github/workflows/ci.yml` runs the offline suite
    across Python 3.8–3.14, a native Termux/aarch64 container job, and a ruff
    lint job.
16. **Type coverage** — DONE. `idun/py.typed` (PEP 561) shipped and registered
    in `setup.py` `package_data`; full annotations on the public API.
17. **Documentation** — DONE. README.md rewritten for v1.0 (config, structured
    output, chains, themes, discovery, MCP parity, async, security). This
    roadmap finalized.
18. **Post-install verification** — DONE. `test.sh` builds a fresh wheel,
    installs into a `mktemp` temp dir with trap-cleanup, runs the offline suite
    against the isolated install, then asserts `idun` / `idun-multi` /
    `idun-mcp` resolve to this package. `install.sh` checks Python ≥ 3.8 + pip
    and installs editable (no-deps). Real E2E run caught + fixed an
    `args.json` regression in the streaming path.
19. **Security pass** — DONE (and documented in README "Security"). Secrets via
    `getpass`, never argv; token files 0600 in a 0700 dir; error bodies
    redacted before logs; `_require_http_url` SSRF guard (no `file://`); no
    bundled tenant/resource; token inspection secret-free.

---

## 7b. Post-v1.0 maintenance (v1.0.1 → v1.0.6) — DONE

Follow-up fixes that shipped after the original v1.0 sign-off:

1. **Welcome → wizard redirect removed (v1.0.6)** — `idun welcome` no longer
   auto-launched the interactive setup wizard (the "broken redirect": the
   banner + cmatrix would drop the user straight into a blocking `input()`
   prompt they could not exit). `show_welcome_then_wizard()` was deleted;
   `cmd_welcome` now only renders the banner (cmatrix flourish preserved,
   guarded by the hard terminal reset) and points the user at `idun wizard`.
2. **Wizard UX rework (v1.0.6)** — `idun wizard` gained:
   - **More choice** — added option `5) other` for ANY generic
     OpenAI-compatible endpoint (base URL + key + model), so non-listed
     vendors work with zero registry changes.
   - **Skip** — `s` keeps registry defaults (no provider written); only
     prompts for the theme.
   - **Quit** — `q` / empty / Ctrl-C / EOF at any prompt aborts cleanly
     (rc 0, no config written, shell left usable). The wizard is now
     exit-able.
   - **TTY safety** — a piped / non-interactive invocation exits 1 with a
     clear message instead of hanging on `input()`.
   Tests: `tests/test_wizard.py` (5 cases) + regression guard in
   `tests/test_welcome.py`.

---

## 7. Risk register

| Risk | Mitigation |
|---|---|
| Console-script name `idun` is generic and gets hijacked (F1) | doctor check (item 4); `test.sh` asserts scripts resolve to this package |
| Provider model slugs rot (F5) | live model discovery (item 13) |
| Hardcoded Azure resource in the registry default | RESOLVED in v0.2.1 |
| API keys in plaintext under `~/.idun` | 0600 (atomic in v0.2.2) |
| API key leaks via argv / process table | RESOLVED in v0.2.2 (`getpass` only) |
| Rate limits during `race` | backoff (item 8) + cache (item 7) |
| Secrets in provider error bodies | RESOLVED in v0.2.2 (redaction) |
| `file://` SSRF via malicious `IDUN_*_BASE` | RESOLVED in v1.0 (`_require_http_url`) |

---

## 8. Post-v1.0 backlog (future, not blocking)

1. **Cost accounting** (item 5) — per-provider price table for `race`.
2. **Provider expansion** — Perplexity, Fireworks, Novita, etc. (one `Provider`
   row each). v1.0 ships 14 providers (incl. Nous Research / Hermes).
3. **OS keyring** backend for credentials (optional, behind the file store).
4. **Support matrix docs** — streaming / tools / vision / JSON mode per provider.

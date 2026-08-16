# Idun SDK — Rework Roadmap (v0.2.0 → v1.0)

Status of this document: written after a full audit of the installed SDK on
Termux/Android. Everything under "Done" was implemented and verified live in
this session; everything below it is planned work.

---

## 1. Audit findings (what was actually broken)

### F1 — `idun wizard` reported "no model found"  [FIXED]
Not an SDK bug. `$PREFIX/bin/idun` had been **overwritten by a different
project** on Aug 15 17:10. The shim read:

```python
from llamacpp_vulkan import main     # llama.cpp Vulkan launcher
```

That launcher takes a mandatory positional `model` argument, so `idun wizard`
was parsed as "load a GGUF model named `wizard`" → `ERROR: model not found`.
The Idun CLI itself was fine the whole time (`python3 idun_cli.py wizard`
started the wizard correctly).

Root cause: two projects claiming the same console-script name, with no
namespacing and no post-install verification.

Fix applied: reinstalled the package (`pip install -e . --no-deps`), which
restored `from idun_cli import main`.

### F2 — Editable install was stale  [FIXED]
`pip show idun-sdk` reported **0.1.28** while the repo was at **0.1.38**. Ten
releases of code were never re-registered, so entry points and metadata
diverged from the source tree.

### F3 — Wizard crashed on non-interactive stdin  [FIXED]
`cmd_wizard` called `input()` unguarded → `EOFError` traceback when run under
a pipe, cron or CI. Now detects a non-TTY and prints the non-interactive
alternative instead of crashing.

### F4 — Backends were hand-wired, not a registry  [FIXED]
`idun/backends.py` had one `load_*_token` / `save_*_token` / `complete_*`
triplet per provider (~275 lines for 4 providers) plus a `run_external()`
if-chain. Adding a provider meant editing 4 places. Nothing was normalized:
each backend returned a bare `(text, model)` tuple, so token usage and latency
were thrown away.

### F5 — Stale model identifiers  [FIXED]
The OpenRouter default was `meta-llama/llama-3.3-70b-instruct:free`, which the
live API now rejects with HTTP 404 ("This model is unavailable for free").
No provider had a way to override the base URL per provider either.

### F6 — GitHub Models backend is dead weight
`models.inference.ai.azure.com` returns 404 for plain PATs (it is Copilot/VS
Code bound). The code carried a long apologetic comment instead of removing
it. Now aliased onto the `openai` transport.

---

## 2. Done in v0.2.0 (implemented + verified)

### Provider registry — `idun/providers.py`
A declarative registry replaces the hand-wired backends. Adding a provider is
now a single `Provider(...)` entry.

* **13 providers**: azure, openai, anthropic, groq, openrouter, together,
  deepseek, mistral, gemini, xai, hf, ollama, local
* **3 transports** cover all of them: `openai` (the /v1/chat/completions
  dialect, 10 providers), `anthropic` (native messages API), `hf`
  (Inference API), plus `azure` delegating to the existing tool-agent client
* **Normalized `Completion`** dataclass: text, model, provider, prompt/completion
  tokens, latency_ms, raw payload
* **Credential resolution order**: provider env keys → `~/.idun/<id>.token`
  (0600, dir 0700). Keys are never echoed; `login` uses `getpass`
* **Per-provider env overrides**: `IDUN_<ID>_MODEL`, `IDUN_<ID>_BASE` — so any
  OpenAI-compatible proxy, vLLM or LiteLLM endpoint works without code changes
* Stdlib-only (`urllib`), so it still runs headless on Termux

### 16-bit retro UI — `idun/retro.py`
Nostalgia layer, pure ANSI, no dependencies.

* Fixed **16-colour palette** mapped to semantic roles (frame/title/accent/ok/
  warn/err/muted)
* **Double-line box drawing** with auto-sizing, embedded-newline explosion and
  ANSI-aware padding — frames never go ragged, even around coloured content
* Blocky `█░` progress bars, spinner, chunky `header()` bars, typewriter output
* Colour-cycled block-letter **IDUN logo**
* Graceful degradation: `NO_COLOR`, `IDUN_NO_RETRO`, `IDUN_ASCII` (pure ASCII,
  encodes to `ascii` without raising), `IDUN_FORCE_COLOR` for pipes

### New CLI — `idun-multi`
| command | purpose |
|---|---|
| `providers` | all 13 providers with model + credential state |
| `models` | known model ids, base, auth for one provider |
| `login` | store a key via hidden prompt (0600) |
| `ask` | one prompt to the active/selected provider |
| `race` | **fan one prompt at N providers in parallel**, compare latency/tokens |
| `doctor` | environment + credential audit, ready/unconfigured split |
| `wizard` | interactive 16-bit setup, TTY-safe |
| `banner` | retro self-test |

### Live verification (real network calls, not mocks)
* `openrouter` + `meta-llama/llama-3.3-70b-instruct` → "MULTIPROVIDER OK",
  904 ms, 27 tokens
* Base-URL override (`IDUN_OPENAI_BASE`) against a proxy with model
  `hermes-4-70b` → "PROXY OK", 533 ms, 35 tokens
* `race` across 3 providers: winner rendered with latency table, the two
  unconfigured/401 providers degraded to readable `ERROR` boxes
* `idun wizard` works again after the shim repair

### Tests
* **27 new offline tests** (`tests/test_providers_retro.py`): registry
  invariants, credential precedence + 0600 perms, response normalization for
  all 3 shapes, usage extraction, system-prompt plumbing, error wrapping, and
  renderer geometry (equal-width boxes under colour, ANSI-aware table
  alignment, ASCII mode)
* **Full suite: 74/74 passing**, no regression in the existing 47

---

## 3. Planned — v0.3 (next)

1. **Streaming** (`--stream`): SSE parsing for the openai/anthropic transports,
   rendered through the retro typewriter for a genuine 16-bit teletype feel.
2. **Interactive REPL** (`idun-multi shell`): persistent multi-turn session,
   `/model`, `/provider`, `/system`, `/save`, `/clear` slash commands, history
   in `~/.idun/history`.
3. **Retire `backends.py`**: keep a thin shim re-exporting from `providers.py`
   for one minor version, emit `DeprecationWarning`, then delete.
4. ~~**Console-script collision guard**~~ — **DONE in v0.2.0**: `idun-multi
   doctor` now reads each installed console script, verifies it imports this
   package, names the hijacking module when it does not, and exits 2. Verified
   against a simulated `llamacpp_vulkan` hijack; 2 regression tests added.
5. **Cost accounting**: per-provider price table, so `race` reports cents per
   answer next to latency.

## 4. Planned — v0.4

6. **Fallback chains**: `IDUN_CHAIN=groq,openrouter,openai` — try in order on
   rate-limit/5xx, report which link served the answer.
7. **Response caching**: content-hash cache in `~/.idun/cache`, `--no-cache`
   to bypass; big win on metered mobile connections.
8. **Retry with backoff**: honour `Retry-After`, exponential jitter, cap.
9. **Config file**: `~/.idun/config.toml` as the primary source (env still
   wins), replacing append-only `~/.idunrc` shell exports.
10. **Structured output**: `--json` on every command for scripting, and
    `--schema` for JSON-mode/tool-calling where the provider supports it.

## 5. Planned — v0.5

11. **MCP server parity**: expose `providers`, `ask`, `race` as MCP tools so
    the registry is usable from any MCP client, not just the CLI.
12. **Async client**: `AsyncIdunClient` for concurrent fan-out without the
    thread pool.
13. **Model discovery**: `GET /v1/models` per provider to replace the
    hardcoded `models=(...)` tuples with live data (cached).
14. **Theme system**: selectable retro palettes — C64, Game Boy DMG-01,
    Amiga Workbench, IBM CGA — via `IDUN_THEME`.

## 6. Toward v1.0

15. **CI matrix**: GitHub Actions across Python 3.8–3.14, plus a Termux
    aarch64 job, running the offline suite; live provider tests gated behind
    repo secrets and marked `@pytest.mark.live`.
16. **Type coverage**: full annotations, `py.typed` marker, mypy/pyright clean
    in strict mode.
17. **Documentation**: per-provider setup pages, a "bring your own endpoint"
    guide, and an honest support matrix (which provider supports streaming,
    tools, vision, JSON mode).
18. **Post-install verification** in `install.sh` + a canonical `test.sh` that
    runs from a fresh clone in a `mktemp` dir with its own PREFIX and
    trap-cleanup, asserting that `idun`, `idun-multi` and `idun-mcp` all
    resolve to this package.
19. **Security pass**: confirm no key ever reaches argv (it leaks via `ps`),
    logs, or the raw payload dumps; document rotation.

---

## 7. Risk register

| Risk | Mitigation |
|---|---|
| Console-script name `idun` is generic and gets hijacked (F1) | doctor check (item 4); consider `idun` → thin dispatcher |
| Provider model slugs rot (F5) | live model discovery (item 13) |
| ~~Hardcoded Azure resource in the registry default~~ | **RESOLVED in v0.2.1**: no tenant ships in the package. `IDUN_BASE`/`IDUN_PROJECT`/`IDUN_AGENT`/`IDUN_TENANT` are read from env; Entra defaults to the multi-tenant `organizations` endpoint; `IdunClient()` raises when unconfigured instead of targeting a foreign resource. 21 guard tests fail the build if any tenant identifier reappears. |
| API keys in plaintext under `~/.idun` | 0600 today; optional OS keyring later |
| Rate limits during `race` | backoff (item 8) + cache (item 7) |

## 8. Immediate next actions

1. Commit v0.2.0 (registry + retro + `idun-multi` + 27 tests).
2. Implement the doctor collision guard (item 4) — it is the highest-value
   item, since it catches the exact bug that started this rework.
3. Then streaming (item 1) and the REPL (item 2).

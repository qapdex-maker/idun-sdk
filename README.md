# Idun SDK

[![Azure AI Foundry](https://img.shields.io/badge/Azure%20AI%20Foundry-NatureLM--Idun--5--MoE-8b5cf6)](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11)
[![PyPI version](https://img.shields.io/pypi/v/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://pypi.org/project/idun-sdk/)
[![stdlib-only](https://img.shields.io/badge/stdlib--only-%E2%9C%93-7c3aed.svg)](https://pypi.org/project/idun-sdk/)

**Thin, stdlib-only client + CLI for the [NatureLM-Idun-5-MoE](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11) agent on Azure AI Foundry — plus a 17-provider registry, a 16-bit retro console, and an MCP server that exposes the whole registry.**

Runs headless on Termux/Android with nothing but the Python standard library
(no `httpx`, no `azure-identity`, no Flask). Idun is a **tool agent** (reasons +
calls tools like `web_search`); this SDK surfaces the **full agent trajectory**
(reasoning + tool calls) instead of a black-box answer.

## What's in the box (v1.0.7)

- **`idun welcome`** — a pure-ASCII banner (no external `cmatrix` dependency;
  the shell is always left usable via a hard terminal reset).
- **17-provider registry** over 3 transports (OpenAI-compatible, Anthropic,
  Hugging Face). Any OpenAI-compatible endpoint works with zero code changes.
- **`idun-multi`** — a 16-colour ANSI "16-bit" console with provider switching,
  an **always-exit-able setup wizard** (`idun wizard`: options `1-5`, `s` skip,
  `q` quit), model discovery, fallback chains, themes, and a REPL.
- **Config file** `~/.idun/config.toml` as the primary config source
  (env vars still win; registry defaults are the fallback).
- **Structured output** — `--json` on any command and a `schema` command.
- **Fallback chains** — fan a prompt across providers until one answers
  (`IDUN_CHAIN`).
- **Theme system** — `classic` / `c64` / `gameboy` / `amiga` / `cga`.
- **Live model discovery** — `GET {base}/models`, cached 24h.
- **MCP server parity** — `idun_providers`, `idun_ask`, `idun_race` alongside
  the original `idun_chat` / `idun_trace` / `idun_export` / `idun_token` tools.
- **Async client** — `AsyncIdunClient` for concurrent fan-out via asyncio.
- **Verified install** — `test.sh` builds a fresh wheel, installs it into a
  temp dir, runs the offline suite, and asserts the console scripts resolve
  to this package.
- **CI** — Python 3.8–3.14 matrix + a native Termux/aarch64 job + ruff lint.

## Quick start

```bash
pip install idun-sdk          # or: ./install.sh  (editable, no-deps)
./test.sh                     # post-install verification (offline, isolated)
idun-multi doctor             # env + credential + console-script audit
```

```bash
idun-multi providers                    # all 17 providers + credential state
idun-multi login --provider groq        # hidden prompt -> ~/.idun/groq.token (0600)
idun-multi ask "explain MoE routing"    # active provider
idun-multi -p openrouter ask "hi"       # one-off provider
idun-multi race "Name one planet."      # fan one prompt at every ready provider
idun-multi models --discover            # live model list for the active provider
idun-multi theme c64                     # switch retro palette
idun-multi doctor                       # env + credential + console-script audit
```

### First-run setup wizard

`idun wizard` is an interactive, TTY-only setup helper. It is **always
exit-able** — at any prompt type `q` (or press Ctrl-C / Ctrl-D) to abort with
no changes and a clean shell. Options:

```bash
idun wizard
```

- `1` Azure · `2` Hugging Face · `3` GitHub Models · `4` OpenAI
- `5` **other** — ANY OpenAI-compatible endpoint (base URL + key + model),
  so vendors not in the registry work with zero code changes
- `s` **skip** — keep registry defaults, only choose a theme
- `q` **quit** — exit without writing anything

The wizard writes benign settings to `~/.idun/config.toml` (mode 0600) and
secrets to per-provider `~/.idun/<id>.token` files (mode 0600). A short
connection probe runs at the end; if it fails (e.g. the key is not live yet)
the wizard still finishes and just prints a neutral hint — nothing is
blocked. Non-interactive (piped) invocations exit with a clear message
instead of hanging.

| Provider | Transport | Credential | Tier |
|---|---|---|---|
| `azure` | Foundry responses | Entra device-code (`idun login`) | paid |
| `openai` | openai | `OPENAI_API_KEY` | paid |
| `anthropic` | anthropic messages | `ANTHROPIC_API_KEY` | paid |
| `groq` | openai | `GROQ_API_KEY` | free tier |
| `openrouter` | openai | `OPENROUTER_API_KEY` | free tier |
| `together` | openai | `TOGETHER_API_KEY` | paid |
| `deepseek` | openai | `DEEPSEEK_API_KEY` | paid |
| `mistral` | openai | `MISTRAL_API_KEY` | paid |
| `gemini` | openai | `GEMINI_API_KEY` | free tier |
| `xai` | openai | `XAI_API_KEY` | paid |
| `nous` | openai | `NOUS_API_KEY` | free tier |
| `hf` | hf inference | `HF_TOKEN` (optional) | free |
| `ollama` | openai | none (local) | free |
| `local` | openai | none | free |
| `perplexity` | openai | `PERPLEXITY_API_KEY` | paid |
| `fireworks` | openai | `FIREWORKS_API_KEY` | paid |
| `novita` | openai | `NOVITA_API_KEY` | paid |

**Any OpenAI-compatible endpoint works without code changes** — override per
provider with `IDUN_<ID>_BASE` and `IDUN_<ID>_MODEL`:

```bash
export IDUN_LOCAL_BASE=http://127.0.0.1:8080/v1   # llama.cpp / vLLM / LiteLLM
idun-multi -p local ask "hello"
```

### Azure Foundry: bring your own resource

**No tenant is bundled with this package.** The `azure` provider is configured
entirely from the environment, and `IdunClient()` raises a clear error rather
than pointing you at somebody else's resource:

```bash
export IDUN_BASE=https://<your-resource>.services.ai.azure.com
export IDUN_PROJECT=<your-project>
export IDUN_AGENT=<your-agent>          # optional, default NatureLM-Idun-5-MoE
export IDUN_TENANT=<your-tenant-guid>   # optional, default "organizations"
idun login                              # Entra device-code
```

Persist them in `~/.idunrc` (mode 0600, outside the repo) and
`source ~/.idunrc`. Every other provider works with no Azure config at all.

Python API:

```python
from idun.providers import complete, list_providers

c = complete("groq", "Summarise MoE routing in one line.")
print(c.text, c.model, c.latency_ms, c.total_tokens)
```

Credentials resolve from the provider env keys first, then
`~/.idun/<id>.token` (file 0600, dir 0700). Keys are never echoed and never
passed via argv.

## Configuration file

`~/.idun/config.toml` is the primary config source. Resolution order is
**env var > `~/.idun/config.toml` > registry default**, so whatever you put in
the file is always overridable from the shell without editing it.

```toml
[defaults]
provider = "groq"
theme    = "c64"

[providers.groq]
model = "llama-3.3-70b-versatile"
base  = "https://api.groq.com/openai/v1"

[providers.openai]
model = "gpt-4o-mini"
```

The file is parsed by a stdlib-only TOML reader (no `tomllib` requirement, so
it works on Python 3.8+). A corrupt or malformed file never crashes startup —
you get a clear warning and the registry defaults are used instead.

## Structured output

Every command that produces a completion supports `--json`, which emits a
single completion-shaped JSON object at the end (streaming still prints
chunks live in non-JSON mode). Use the `schema` command to inspect the
response schema per provider, including whether `json_mode` is supported:

```bash
idun-multi ask "What is a MoE?" --json
idun-multi schema groq
```

```json
{"provider": "groq", "model": "llama-3.3-70b-versatile",
 "text": "...", "prompt_tokens": 7, "completion_tokens": 23,
 "total_tokens": 30, "latency_ms": 412, "raw": {...}}
```

## Fallback chains

`IDUN_CHAIN` lists providers to try in order; the first one that returns a
non-retryable answer wins, and the chosen link is recorded in `raw._served_by`:

```bash
export IDUN_CHAIN=groq,openrouter,openai
idun-multi ask "Ansible vs Terraform, one line."   # tries groq, then openrouter, then openai
```

Skipped links on 429 / 5xx / auth / transport errors are reported in
`raw._chain`. Programmatic:

```python
from idun.providers import complete_chain
c = complete_chain(["groq", "openrouter"], "hi")
print(c.raw["_served_by"])
```

## Themes

The 16-colour chrome is selectable via `IDUN_THEME` (read at import) or the
`theme` command. Palettes: `classic` (default), `c64`, `gameboy`, `amiga`,
`cga`. Unknown ids fall back to `classic`.

```bash
idun-multi theme gameboy
```

`NO_COLOR=1` / `IDUN_NO_RETRO=1` disable colour entirely, `IDUN_ASCII=1`
swaps box-drawing for pure ASCII, `IDUN_FORCE_COLOR=1` keeps colour through a
pipe, and `IDUN_NO_TYPEWRITER=1` prints answers instantly.

## Model discovery

`models` shows the registry model list; `--discover` fetches the live
`GET {base}/models` endpoint and caches it under `~/.idun/models/<id>.json`
for 24h (override with `IDUN_MODELS_CACHE_MAX_AGE`, disable with
`IDUN_NO_MODELS_CACHE`). On any error or for non-OpenAI transports, the
registry list is returned so callers always get something usable.

```bash
idun-multi models groq --discover
```

## MCP server

`idun_mcp.py` is a zero-dependency stdio MCP server (no FastMCP / httpx):

```bash
python3 idun_mcp.py
```

Tools exposed:

| Tool | Purpose |
|---|---|
| `idun_chat` | final answer from the Idun agent |
| `idun_trace` | full trajectory (steps + text) |
| `idun_export` | trajectory as JSON / Markdown |
| `idun_token` | inspect stored token state (no secret leak) |
| `idun_providers` | list the registry + credential state |
| `idun_ask` | send one prompt to ANY provider in the registry |
| `idun_race` | fan one prompt at several providers (latency + state) |

Add to any MCP client:

```json
{ "mcpServers": { "idun": { "command": "python3", "args": ["/abs/path/idun-sdk/idun_mcp.py"] } } }
```

## Async client

```python
import asyncio
from idun.async_client import AsyncIdunClient

async def main():
    c = AsyncIdunClient()
    results = await c.gather(
        c.acomplete("groq", "hi"),
        c.acomplete("openai", "hi"),
    )
    for r in results:
        print(r.text)

asyncio.run(main())
```

`AsyncIdunClient` runs each (blocking) stdlib HTTP call in a worker thread via
`asyncio.to_thread` — no dedicated thread pool — so the event loop stays free
for concurrent fan-out.

## Security

- **Secrets are never on the command line.** `idun-multi login` reads keys with
  `getpass` (hidden input); they are written to `~/.idun/<id>.token` (mode 0600,
  inside a 0700 dir), never echoed, never logged.
- **Optional OS keyring (opt-in).** If you install the `keyring` package and set
  `IDUN_KEYRING=1` (or `secrets_backend = "keyring"` in `~/.idun/config.toml`),
  credentials are additionally mirrored to your OS credential store (Keychain /
  Credential Manager / Secret Service). The file store stays primary and always
  wins; the keyring is a secondary fallback and is only consulted when no
  file/env/config secret exists. No third-party dependency is required unless
  you opt in. `idun-multi doctor` reports the active secret backend.
- **Error bodies are sanitised.** Upstream error responses are truncated and
  scrubbed before they reach stderr/logs, so a token accidentally echoed by a
  provider is never relayed back.
- **SSRF guard.** Every outbound request is validated to be `http://`/`https://`
  via `_require_http_url` before any connection is made — `file://`, `gopher://`,
  and similar schemes are rejected, so a malicious `IDUN_*_BASE` cannot read
  local files.
- **No bundled tenant/resource.** The Azure provider is configured purely from
  your environment; the package ships no credentials and no default resource.
- **Token inspection is secret-free.** `idun token` / the `idun_token` MCP tool
  report validity, expiry, and the account UPN — never the bearer token itself.

## Azure request shape (verified)

```
POST {base}/api/projects/{project}/agents/{agent}/endpoint/protocols/openai/responses?api-version=2025-05-15-preview
Authorization: Bearer ***
{"model": "model-router", "input": "<prompt>", "max_output_tokens": 4096}
```

- `model` MUST be `"model-router"` (agent id is in the URL).
- Do **not** send a `tools` key — the agent owns its tools (else `400 invalid_payload`).

## Install & verify

```bash
pip install idun-sdk          # or: ./install.sh
./test.sh                     # builds a wheel, installs into a temp dir,
                              # runs the offline suite, asserts console
                              # scripts resolve to THIS package
```

Requires Python ≥ 3.8; **no third-party dependencies** (stdlib-only, runs
headless on Termux/Android).

## Links

- PyPI: https://pypi.org/project/idun-sdk/
- Repo: https://github.com/qapdex-maker/idun-sdk
- Foundry: https://ai.azure.com

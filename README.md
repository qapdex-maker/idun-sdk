# Idun SDK

[![Azure AI Foundry](https://img.shields.io/badge/Azure%20AI%20Foundry-NatureLM--Idun--5--MoE-8b5cf6)](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11)
[![PyPI version](https://img.shields.io/pypi/v/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://pypi.org/project/idun-sdk/)
[![stdlib-only](https://img.shields.io/badge/stdlib--only-%E2%9C%93-7c3aed.svg)](https://pypi.org/project/idun-sdk/)

<p align="center">
  <img src="https://raw.githubusercontent.com/qapdex-maker/idun-sdk/main/idun/data/foundry_logo_color.svg" width="104" height="110" alt="Azure AI Foundry logo"/>
</p>

**Thin, stdlib-only client + CLI for the [NatureLM-Idun-5-MoE](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11) agent on Azure AI Foundry — plus a 13-provider registry and a 16-bit retro console.**

Runs headless on Termux/Android with nothing but the Python standard library
(no `httpx`, no `azure-identity`, no Flask). Idun is a **tool agent** (reasons +
calls tools like `web_search`); this SDK surfaces the **full agent trajectory**
(reasoning + tool calls) instead of a black-box answer.

## Multi-provider (v0.2.0)

Since v0.2.0 the SDK ships a **declarative provider registry** covering 13
providers over 3 transports, plus `idun-multi`: a 16-bit retro console.

```bash
idun-multi providers                    # all 13 providers + credential state
idun-multi login --provider groq        # hidden prompt -> ~/.idun/groq.token (0600)
idun-multi ask "explain MoE routing"    # active provider
idun-multi -p openrouter ask "hi"       # one-off provider
idun-multi race "Name one planet."      # fan one prompt at every ready provider
idun-multi doctor                       # env + credential + console-script audit
```

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
| `hf` | hf inference | `HF_TOKEN` (optional) | free |
| `ollama` | openai | none (local) | free |
| `local` | openai | none | free |

**Any OpenAI-compatible endpoint works without code changes** — override per
provider with `IDUN_<ID>_BASE` and `IDUN_<ID>_MODEL`:

```bash
export IDUN_LOCAL_BASE=http://127.0.0.1:8080/v1   # llama.cpp / vLLM / LiteLLM
idun-multi -p local ask "hello"
```

Python API:

```python
from idun import complete, list_providers

c = complete("groq", "Summarise MoE routing in one line.")
print(c.text, c.model, c.latency_ms, c.total_tokens)
```

Credentials resolve from the provider env keys first, then
`~/.idun/<id>.token` (file 0600, dir 0700). Keys are never echoed and never
passed via argv.

### Retro UI

The 16-colour ANSI chrome degrades cleanly: `NO_COLOR=1` or `IDUN_NO_RETRO=1`
disables colour, `IDUN_ASCII=1` swaps box-drawing for pure ASCII,
`IDUN_FORCE_COLOR=1` keeps colour through a pipe, `IDUN_NO_TYPEWRITER=1`
prints answers instantly.

## Multi-backend (legacy, pre-0.2)

The same `IdunClient` API dispatches to three interchangeable backends. Non-Azure
backends need no `FOUNDRY_TOKEN`, so the SDK keeps working even when the Azure
subscription is suspended.

| Backend  | Credentials                          | Cost     | Notes |
|----------|--------------------------------------|----------|-------|
| `azure`  | Entra device-code (`idun login`)     | paid     | default; full tool-agent trajectory |
| `hf`     | `HF_TOKEN` / `~/hf_token.txt`        | free     | Hugging Face Inference API; flat answer |
| `github` | `GITHUB_TOKEN` / `~/github_token.txt` | free tier | GitHub Models (OpenAI-compatible); **needs Copilot/VS Code routing — plain PAT returns 404** |
| `openai` | `OPENAI_API_KEY` / `~/openai_token.txt` | paid/free tier | OpenAI-compatible `/v1/chat/completions`; any OpenAI-compatible endpoint via `OPENAI_BASE` |

Set the backend globally via env (`IDUN_BACKEND=hf`) or per-call (`--backend`).
Model overrides: `HF_MODEL`, `GITHUB_MODEL`, `OPENAI_MODEL`, `OPENAI_BASE`.
Non-Azure backends return a flat answer (`res.steps == []`) — the tool-agent
trajectory is an Azure-Idun feature.

## Install

```bash
pip install idun-sdk
```

Installs the `idun` CLI, the `idun` Python package, and the stdlib MCP server
`idun_mcp.py`. Requires Python ≥ 3.8; **no third-party dependencies**
(stdlib-only, runs headless on Termux/Android).

Verify the install:

```bash
idun --help          # shows all commands
idun welcome         # banner + matrix intro
```

## Setup

Idun is backend-agnostic. Pick a backend once with the wizard (writes
`~/.idunrc`, sourced automatically by your shell), or set credentials per
backend. Run the wizard for a guided, universal first-run setup:

```bash
idun wizard          # choose backend, capture creds/config -> ~/.idunrc
source ~/.idunrc     # or restart your shell
idun status          # confirm active backend + credential state
```

### Backend credentials

| Backend  | Setup command                              | Stored at / env            |
|----------|--------------------------------------------|----------------------------|
| `azure`  | `idun login`                               | `~/foundry_token.txt`      |
| `hf`     | `idun login --backend hf`                  | `~/hf_token.txt` / `HF_TOKEN` |
| `github` | `idun login --backend github`              | `~/github_token.txt` / `GITHUB_TOKEN` |
| `openai` | `idun login --backend openai`             | `~/openai_token.txt` / `OPENAI_API_KEY` |

**Azure (default).** `idun login` runs a device-code flow and stores an Entra
bearer token. **No admin role required** — any tenant user with agent RBAC can
run it; admin rights are only needed to *configure* the agent, not to *use* it.
The token auto-rotates before expiry.

**Hugging Face / GitHub.** The wizard or `idun login --backend <x>` prompts for
a token and saves it (0600). Both offer a free tier; no Azure subscription or
card needed.

### Switching backends

Globally via env, or per call via `--backend`:

```bash
export IDUN_BACKEND=hf          # all future calls use HF
idun chat --backend github "Hi" # one-off override
```

Model overrides (optional): `HF_MODEL`, `GITHUB_MODEL`.

### Quick test

```bash
idun chat "Hello"                       # azure (needs login first)
idun chat --backend hf "Hello"          # any backend with creds set
```

## Quickstart

```bash
idun chat "Summarize Contoso's sustainability comms in one sentence."
idun trace --backend azure "Use web_search to find the current CEO of Contoso."
```

```python
from idun import IdunClient

# Azure (default)
res = IdunClient().complete("Your prompt here")
print(res.text)                 # final answer
for s in res.steps:             # agent trajectory
    print(s.kind, s.tool, s.query, s.status)

# Hugging Face (no Azure token needed)
res = IdunClient(backend="hf", hf_token="hf_xxx",
                 hf_model="microsoft/phi-3-mini-4k-instruct").complete("Hello")
print(res.text)
```

## Commands

| Command | Purpose |
|---------|---------|
| `idun wizard` | universal first-run setup |
| `idun login [--backend X]` | store backend credentials |
| `idun status` | show active backend + credential state |
| `idun chat` | final answer only |
| `idun trace` | full trajectory (steps + text) |
| `idun export` | trajectory as JSON / Markdown |
| `idun packs` / `idun run` | curated prompt packs (e.g. Contoso) |
| `idun diff` | side-by-side trace diff of two prompts |
| `idun token` | inspect / refresh the Foundry token |
| `idun logo` | print the Foundry logo |

## Hugging Face pipeline

The `hf` command wraps the Hugging Face Hub + Inference API (stdlib-only for
`whoami` / `status`; `push` uses the optional `huggingface_hub` client):

```bash
idun hf whoami                              # validate token, show HF user
idun hf status microsoft/phi-3-mini-4k-instruct   # exists? gated? private? task?
idun hf push Qapdex/my-agent-out a.txt b.txt       # create repo + upload files
```

`push` needs `pip install huggingface_hub` (kept optional so the SDK stays
stdlib-only for everything else). Upload under your **user** namespace
(`Qapdex/...`), not an org, unless your token has write rights there.

## MCP server

`idun_mcp.py` is a zero-dependency stdio MCP server (no FastMCP / httpx):

```bash
python3 idun_mcp.py
```

Exposes `idun_chat(prompt)` and `idun_trace(prompt)`. Add to any MCP client:

```json
{ "mcpServers": { "idun": { "command": "python3", "args": ["/abs/path/idun-sdk/idun_mcp.py"] } } }
```

Docs mirror (GitMCP): `https://gitmcp.io/qapdex-maker/idun-sdk/sse`

## Combine with Sentry (MCP)

Idun pairs well with [Sentry's MCP server](https://github.com/getsentry/sentry-mcp)
so an agent can both *call* Idun and *inspect* Sentry errors. Add it remotely
(OAuth, note the `/mcp` suffix):

```json
{ "mcpServers": { "sentry": { "url": "https://mcp.sentry.dev/mcp" } } }
```

Recommended combo: `idun` (calls the agent) + `idun-docs` (reads SDK docs) +
`sentry` (queries error tracking).

## Azure request shape (verified)

```
POST {base}/api/projects/{project}/agents/{agent}/endpoint/protocols/openai/responses?api-version=2025-05-15-preview
Authorization: Bearer ***
{"model": "model-router", "input": "<prompt>", "max_output_tokens": 4096}
```

- `model` MUST be `"model-router"` (agent id is in the URL).
- Do **not** send a `tools` key — the agent owns its tools (else `400 invalid_payload`).

## Links

- PyPI: https://pypi.org/project/idun-sdk/
- Repo: https://github.com/qapdex-maker/idun-sdk
- Foundry: https://ai.azure.com

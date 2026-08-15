# Idun SDK

[![Azure AI Foundry](https://img.shields.io/badge/Azure%20AI%20Foundry-NatureLM--Idun--5--MoE-8b5cf6)](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11)
[![PyPI version](https://img.shields.io/pypi/v/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://pypi.org/project/idun-sdk/)
[![stdlib-only](https://img.shields.io/badge/stdlib--only-%E2%9C%93-7c3aed.svg)](https://pypi.org/project/idun-sdk/)

<p align="center">
  <img src="https://raw.githubusercontent.com/qapdex-maker/idun-sdk/main/idun/data/foundry_logo_color.svg" width="104" height="110" alt="Azure AI Foundry logo"/>
</p>

**Thin, stdlib-only client + CLI for the [NatureLM-Idun-5-MoE](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11) agent on Azure AI Foundry — with a pluggable multi-backend layer.**

No `httpx`, no `azure-identity`, no Flask — it runs headless on Termux/Android with
nothing but the Python standard library. Idun is a **tool agent** (it reasons and
calls tools like `web_search`); this SDK surfaces the **full agent trajectory**
(reasoning steps + tool calls) instead of a black-box answer.

**Multi-backend (v0.1.31+):** the same `IdunClient` API dispatches to
`azure` (default), `hf` (Hugging Face), `github` (GitHub Models), or `ollama`
(local). Non-Azure backends need no Foundry token, so Idun keeps working even
when the Azure subscription is suspended.

---

## Install

```bash
pip install idun-sdk
```

Installs the `idun` CLI, the `idun` Python package, and the stdlib MCP server
`idun_mcp.py`.

## Authenticate

```bash
idun login          # device-code flow, token saved to ~/foundry_token.txt
```

**No admin role required** — `idun login` returns a plain Entra bearer token for
the Foundry endpoint. Any tenant user with agent access (RBAC) can run it; admin
rights are only needed to *configure* the agent, not to *use* it. The token
auto-rotates before expiry.

## Quickstart

```bash
# final answer only
idun chat "Summarize Contoso's sustainability communications in one sentence."

# full agent trajectory (reasoning + tool steps)
idun trace "Use web_search to find the current CEO of Contoso."
```

```python
from idun import IdunClient

res = IdunClient().complete("Your prompt here")
print(res.text)                 # final answer
for s in res.steps:             # agent trajectory
    print(s.kind, s.tool, s.query, s.status)
```

## Features

| Command | Purpose |
|---------|---------|
| `idun chat` | final answer only |
| `idun trace` | full trajectory (steps + text) |
| `idun export` | trajectory as JSON / Markdown |
| `idun packs` / `idun run` | curated prompt packs (e.g. Contoso) |
| `idun diff` | side-by-side trace diff of two prompts |
| `idun token` | inspect / refresh the Foundry token |
| `idun logo` | print the Foundry logo |

## Multi-backend (no Foundry dependency)

Idun runs on four interchangeable backends behind the **same** `IdunClient`
API. Non-Azure backends need no `FOUNDRY_TOKEN`, so the SDK keeps working even
when the Azure subscription is suspended.

```bash
idun wizard                 # universal first-run setup -> writes ~/.idunrc
idun status                 # show active backend + credential state
idun login --backend hf     # store a Hugging Face token
idun chat --backend github "Hello"   # one-shot backend override
```

| Backend  | Credentials                         | Cost     | Notes |
|----------|-------------------------------------|----------|-------|
| `azure`  | Entra device-code (`idun login`)    | paid     | default; full tool-agent trajectory |
| `hf`     | `HF_TOKEN` / `~/hf_token.txt`       | free tier| serverless Inference API; flat answer |
| `github` | `GITHUB_TOKEN` / `~/github_token.txt` | free tier | GitHub Models (OpenAI-compatible) |
| `ollama` | local server at `OLLAMA_BASE`      | free     | no cloud; set `OLLAMA_MODEL` |

Set the backend globally via env (`IDUN_BACKEND=hf`) or per-call (`--backend`).
Per-backend model overrides: `HF_MODEL`, `GITHUB_MODEL`, `OLLAMA_BASE`,
`OLLAMA_MODEL`.

```python
from idun import IdunClient

# Hugging Face (no Azure token needed)
res = IdunClient(backend="hf", hf_token="hf_xxx", hf_model="microsoft/phi-3-mini-4k-instruct")
print(res.complete("Hello").text)

# GitHub Models (free)
res = IdunClient(backend="github", github_token="ghp_xxx").complete("Hi")
```

Note: non-Azure backends return a flat answer (`res.steps == []`) — the
tool-agent trajectory (reasoning + `web_search`) is an Azure-Idun feature.

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
so an agent can both *call* Idun and *inspect* Sentry errors/traces. Sentry
MCP is a separate, optional provider — the Idun SDK stays stdlib-only.

Remote (zero-setup, OAuth — **note the `/mcp` suffix**):

```json
{ "mcpServers": { "sentry": { "url": "https://mcp.sentry.dev/mcp" } } }
```

Stdio (OAuth via `mcp-remote`, no static token needed):

```json
{ "mcpServers": { "sentry": { "command": "npx", "args": ["-y", "mcp-remote@latest", "https://mcp.sentry.dev/mcp"] } } }
```

Authenticate once (opens a browser for the OAuth flow):

```
/mcp auth sentry
```

Recommended combo for a foreign agent: `idun` (calls the agent) + `idun-docs`
(reads the SDK docs) + `sentry` (queries error tracking). The agent can invoke
Idun and, when a call fails, pull the correlated Sentry issue on its own.

## Request shape (verified)

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

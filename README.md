# Idun SDK

[![Azure AI Foundry](https://img.shields.io/badge/Azure%20AI%20Foundry-NatureLM--Idun--5--MoE-8b5cf6)](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11)
[![PyPI version](https://img.shields.io/pypi/v/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://pypi.org/project/idun-sdk/)
[![stdlib-only](https://img.shields.io/badge/stdlib--only-%E2%9C%93-7c3aed.svg)](https://pypi.org/project/idun-sdk/)

<p align="center">
  <img src="https://raw.githubusercontent.com/qapdex-maker/idun-sdk/main/idun/data/foundry_logo_color.svg" width="104" height="110" alt="Azure AI Foundry logo"/>
</p>

**Thin, stdlib-only client + CLI for the [NatureLM-Idun-5-MoE](https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11) agent on Azure AI Foundry.**

No `httpx`, no `azure-identity`, no Flask — it runs headless on Termux/Android with
nothing but the Python standard library. Idun is a **tool agent** (it reasons and
calls tools like `web_search`); this SDK surfaces the **full agent trajectory**
(reasoning steps + tool calls) instead of a black-box answer.

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
- Foundry: https://ai.azure.com/nextgen/agents/daf452cd-804f-41ed-9cfe-cb8f73140d4e/preview?version=11

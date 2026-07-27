# Idun SDK

Thin client + CLI for the **NatureLM-Idun-5-MoE** agent on **Azure AI Foundry**.
Stdlib-only (no httpx / azure.identity) so it runs headless on Termux/Android.

Idun is a **tool agent** (it calls `web_search`, `memory_search`). This SDK
surfaces the full agent trajectory — not just the final chat text — so you can
see every reasoning step and tool call instead of a black-box chatbot wheel.

## Install

```bash
pip install idun-sdk        # PyPI: https://pypi.org/project/idun-sdk/
# or, from source:
cd idun-sdk && pip install -e .
```

The `idun` CLI and the `idun` Python package (plus the stdlib MCP server
`idun_mcp.py`) are installed.

## Authenticate (device-code, Entra)

```bash
idun login
# opens https://microsoft.com/devicelogin — enter the printed code,
# sign in with your tenant account (no admin role required).
# Token is saved to ~/foundry_token.txt (FOUNDRY_TOKEN).
```

**No admin role needed.** `idun login` runs a standard Entra device-code
flow and returns a plain bearer access token for the Foundry agent
endpoint. You do **not** become a portal admin — you only get an API token
that the SDK attaches to each request. Any tenant user who has been granted
**access to the NatureLM-Idun-5-MoE agent** (RBAC on the Foundry resource)
can run `idun login`. Admin rights are only needed to *configure or redeploy*
the agent, not to *use* it.

The token is a normal Entra `FOUNDRY_TOKEN` (scope `https://ai.azure.com/.default`);
it auto-rotates before expiry (Phase 2.5).

## Use

```bash
# final answer only
idun chat "Fasse in einem Satz zusammen, was Contoso im Bereich Nachhaltigkeit kommuniziert."

# full agent trajectory (reasoning + web_search tool steps)
idun trace "Use web_search to find the current CEO of Contoso and report the name."
```

### Python

```python
from idun import IdunClient
res = IdunClient().complete("Your prompt here")
print(res.text)            # final answer
for s in res.steps:        # agent trajectory
    if s.kind == "tool":
        print("TOOL", s.tool, s.status, s.query)
    else:
        print("REASON", s.text[:80])
```

## Request shape (verified working)

```
POST {base}/api/projects/{project}/agents/{agent}/endpoint/protocols/openai/responses?api-version=2025-05-15-preview
Authorization: Bearer <FOUNDRY_TOKEN>
Content-Type: application/json

{"model": "model-router", "input": "<prompt string>", "max_output_tokens": 4096}
```

Notes:
- `model` MUST be `"model-router"` (the agent id is already in the URL).
- Do **not** send a `tools` key — the agent owns its capabilities; doing so
  returns `400 invalid_payload`.
- The answer is in `output[].content[].text`; tool calls appear as
  `web_search_call` items with `action.queries` and `status`.

## Files

- `idun/client.py` — `IdunClient` (sync `complete()`) + `_normalize_output()`
- `idun/auth.py` — stdlib device-code `login()` + `load_token()`
- `idun_cli.py` — `idun login | chat | trace`

## MCP — agent + docs

Idun is available as an MCP server **and** has a GitMCP docs mirror, so other
agents can both call Idun and read its documentation without hallucinating.

### 1. Idun MCP server (stdlib-only, local)

`idun_mcp.py` is a zero-dependency stdio MCP server — no FastMCP / httpx
needed (runs on bare Python, ideal for Termux/Android).

```bash
python3 idun_mcp.py        # stdio MCP server
```

Tools exposed:
- `idun_chat(prompt)` — final answer text
- `idun_trace(prompt)` — full agent trajectory (steps + text)

Add to any MCP client (e.g. Cursor `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "idun": { "command": "python3", "args": ["/abs/path/idun-sdk/idun_mcp.py"] }
  }
}
```

### 2. GitMCP docs mirror (remote, zero-setup)

Point an MCP client at the GitMCP URL to give it live access to this repo's
docs + code (prefers `llms.txt`):

```
https://gitmcp.io/qapdex-maker/idun-sdk/sse
```

For stdio-only clients (Claude Desktop, Cline, Msty):

```json
{ "mcpServers": { "idun-docs": { "command": "npx", "args": ["mcp-remote", "https://gitmcp.io/qapdex-maker/idun-sdk/sse"] } } }
```

**Recommended combo for a foreign agent:** both `idun` (calls the agent) and
`idun-docs` (reads the SDK docs) — it can invoke Idun *and* look up the exact
`IdunClient` signature on its own.

[![GitMCP](https://img.shields.io/endpoint?url=https://gitmcp.io/badge/qapdex-maker/idun-sdk)](https://gitmcp.io/qapdex-maker/idun-sdk)


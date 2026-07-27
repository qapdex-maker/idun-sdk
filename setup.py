from setuptools import setup, find_packages

LONG_DESCRIPTION = """\
# Idun SDK

Thin, **stdlib-only** client + CLI for the **NatureLM-Idun-5-MoE** agent on
**Azure AI Foundry** (codename *Idun*). No `httpx`, no `azure-identity` \u2014 it
runs headless on Termux/Android with nothing but the Python standard library.

Idun is a **tool agent**: it reasons and calls tools (`web_search`,
`memory_search`). This SDK surfaces the **full agent trajectory** \u2014 every
reasoning step and tool call \u2014 instead of a black-box chatbot wheel, so you
can see *how* it arrived at an answer.

## Install

```bash
pip install idun-sdk
```

The `idun` CLI and the `idun` Python package (plus the stdlib MCP server
`idun_mcp.py`) are installed.

## Authenticate (device-code, Entra)

```bash
idun login
# opens https://microsoft.com/devicelogin \u2014 enter the printed code,
# sign in with your QMFI-Research admin account.
# Token is saved to ~/foundry_token.txt (FOUNDRY_TOKEN).
```

Alternatively export `FOUNDRY_TOKEN` directly.

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

`IdunResult` has:

- `text` \u2014 the final answer
- `steps` \u2014 list of `Step` (`kind="reasoning"|"tool"`, plus `tool`/`query`/`status` for tool steps)
- `model` \u2014 the backing model (e.g. `gpt-5.4-2026-03-05`)
- `raw` \u2014 the verbatim Foundry responses payload

## Request shape (verified working)

```
POST {base}/api/projects/{project}/agents/{agent}/endpoint/protocols/openai/responses?api-version=2025-05-15-preview
Authorization: Bearer ***
Content-Type: application/json

{"model": "model-router", "input": "<prompt string>", "max_output_tokens": 4096}
```

Notes:

- `model` MUST be `"model-router"` (the agent id is already in the URL).
- Do **not** send a `tools` key \u2014 the agent owns its capabilities; doing so
  returns `400 invalid_payload`.
- The answer is in `output[].content[].text`; tool calls appear as
  `web_search_call` items with `action.queries` and `status`.

## MCP \u2014 agent + docs

Idun is available as an MCP server **and** has a GitMCP docs mirror, so other
agents can both call Idun and read its documentation without hallucinating.

### 1. Idun MCP server (stdlib-only, local)

`idun_mcp.py` is a zero-dependency stdio MCP server \u2014 no FastMCP / httpx
needed (runs on bare Python, ideal for Termux/Android).

```bash
python3 idun_mcp.py        # stdio MCP server
```

Tools exposed:

- `idun_chat(prompt)` \u2014 final answer text
- `idun_trace(prompt)` \u2014 full agent trajectory (steps + text)

Add to any MCP client (e.g. Cursor `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "idun": { "command": "python3", "args": ["/abs/path/idun-sdk/idun_mcp.py"] }
  }
}
```

### 2. GitMCP docs mirror (remote, zero-setup)

```
https://gitmcp.io/qapdex-maker/idun-sdk/sse
```

For stdio-only clients (Claude Desktop, Cline, Msty):

```json
{ "mcpServers": { "idun-docs": { "command": "npx", "args": ["mcp-remote", "https://gitmcp.io/qapdex-maker/idun-sdk/sse"] } } }
```

**Recommended combo for a foreign agent:** both `idun` (calls the agent) and
`idun-docs` (reads the SDK docs) \u2014 it can invoke Idun *and* look up the exact
`IdunClient` signature on its own.

## Why stdlib-only?

Many AI agents run on constrained hosts (Termux on Android, minimal
containers). Pulling `httpx`/`pydantic`/`azure-identity` breaks those setups.
This SDK uses `urllib.request` + `json` only, so `pip install idun-sdk` just
works everywhere Python 3.8+ runs.

## Links

- PyPI: https://pypi.org/project/idun-sdk/
- SDK repo: https://github.com/qapdex-maker/idun-sdk
- Playground repo: https://github.com/qapdex-maker/idun-playground
- GitMCP docs: https://gitmcp.io/qapdex-maker/idun-sdk/sse
"""

setup(
    name="idun-sdk",
    version="0.1.7",
    description="Thin client + CLI for Azure AI Foundry agent NatureLM-Idun-5-MoE",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="QMFI-Research",
    author_email="alexanderkleine@qmfiresearch.onmicrosoft.com",
    url="https://github.com/qapdex-maker/idun-sdk",
    project_urls={
        "Source": "https://github.com/qapdex-maker/idun-sdk",
        "Playground": "https://github.com/qapdex-maker/idun-playground",
        "Docs (GitMCP)": "https://gitmcp.io/qapdex-maker/idun-sdk/sse",
        "Bug Tracker": "https://github.com/qapdex-maker/idun-sdk/issues",
    },
    packages=find_packages(),
    py_modules=["idun_cli", "idun_mcp"],
    package_data={"idun": ["data/*.svg", "data/prompt_packs/*.json"]},
    python_requires=">=3.8",
    # stdlib-only: no runtime dependencies. Works headless on Termux.
    install_requires=[],
    entry_points={"console_scripts": ["idun=idun_cli:main"]},
    keywords=[
        "azure", "ai-foundry", "azure-ai-foundry", "agent", "tool-agent",
        "mcp", "model-context-protocol", "naturelm", "idun", "llm",
        "cli", "stdlib", "termux", "web_search", "trace",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)

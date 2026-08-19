# idun-sdk

[![PyPI](https://img.shields.io/pypi/v/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A thin, dependency-free Python client + CLI for **Azure AI Foundry** agents
(Idun / NatureLM) and any OpenAI-compatible endpoint. Tenant-agnostic by default:
bring your own Foundry resource, no hardcoded tenant coordinates.

---

## Install

```bash
pip install idun-sdk
# with optional PDF ingest:
pip install "idun-sdk[pdf]"   # pulls PyPDF2
```

## Quick start (SDK)

```python
from idun import IdunClient

client = IdunClient()                 # reads ~/.idun/config.toml
out = client.complete("Summarize the quarterly risk report.")
print(out["text"])
```

### Async

```python
import asyncio
from idun import AsyncIdunClient

async def main():
    c = AsyncIdunClient()
    out = await c.acomplete("What changed vs last quarter?")
    print(out["text"])

asyncio.run(main())
```

## CLI

```text
idun chat "your prompt"                    # one-shot completion
idun chat --async "your prompt"           # async path
idun run <pack> <key>                     # run a bundled prompt pack
idun packs                                # list bundled prompt packs
idun login                               # device-code login to your Foundry
idun status                              # show token / config state
idun wizard                              # interactive setup (1-5, s skip, q quit)
idun welcome                             # ASCII banner
idun export <file>                       # export conversation / config
idun matrix  --docs DIR  --questions FILE   # Doc x Question pivot (IDEA α)
idun diff-docs --doc-a A --doc-b B --topics T  # clause-drift compare (IDEA γ)
```

## Supported providers

The `idun` CLI / `IdunClient` speak to any OpenAI-compatible endpoint plus the
native Azure AI Foundry transport. Registered providers (over 3 transports):

- **OpenAI-compatible:** `openai`, `groq`, `together`, `perplexity`, `fireworks`,
  `novita`, `xai`, `deepseek`, `mistral`, `openrouter`
- **Anthropic:** `anthropic` (Claude)
- **Google:** `gemini`
- **Azure:** `azure` (Azure AI Foundry / Idun agent)

Any OpenAI-compatible base URL works with zero code changes — set it in the
config and the provider switches automatically. See
**[SUPPORT_MATRIX.md](./SUPPORT_MATRIX.md)** for per-provider capability details.

## Configuration (tenant-agnostic)

`~/.idun/config.toml` (neutral defaults — supply your own resource):

```toml
[default]
endpoint = "https://YOUR-RESOURCE.services.ai.azure.com"
project  = "your-project"
agent    = "your-agent-name"
token    = "YOUR_TOKEN"   # or use device-code login: `idun login`
```

No QMFI-specific values are baked into the shipped code.

## Additional features

> These build on the core SDK and live in `idun.matrix` / the playground repo.

### Idun Matrix — Doc × Question pivot (IDEA α)

Build an N × M answer matrix over documents × questions. Each cell carries the
answer, the source citation, and a status (GREEN = answered+cited, RED =
contradiction, GRAY = no info).

```bash
idun matrix --docs ./contracts --questions ./questions.txt
```

### Clause Drift compare (IDEA γ)

Compare two documents across topics and flag deviations:

```bash
idun diff-docs --doc-a contract_a.txt --doc-b contract_b.txt --topics topics.txt
```

### PocketPal-style Bridge (IDEA β)

A tenant-agnostic mobile web UI that runs `idun matrix` against *your* Foundry
resource: <https://qapdex-maker.github.io/idun-playground/matrix_app.html>

## Links

- Live demo (recorded trajectories + matrix UI): <https://qapdex-maker.github.io/idun-playground/>
- Matrix concept note: <https://github.com/qapdex-maker/idun-playground/blob/main/DOC_MATRIX_CONCEPT.md>
- Source: <https://github.com/qapdex-maker/idun-sdk>

## Development

```bash
pip install -e ".[dev]"
pytest        # offline; no network/API keys required
ruff check .  # lint (pinned ruff==0.15.10 in CI)
```

## License

MIT.

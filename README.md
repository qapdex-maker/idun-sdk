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

### Two CLIs — two separate setup wizards (intentionally, not one)

This package ships **two** command-line tools with distinct purposes. They are
**intentionally kept separate** — `idun` is the Azure AI Foundry client,
`idun-multi` is the multi-provider LLM console. There is **no** unified
`idun-wizard`; each tool has its **own** first-run setup wizard:

- **`idun`** — the Azure AI Foundry client. Agent completions, trajectory
  export, document matrix (`idun matrix`), prompt packs (`idun run` /
  `idun packs`), and Hugging Face Hub operations (`idun hf`). Azure-specific.
  - `idun wizard` configures the **Azure Foundry client** (endpoint /
    project / agent) in `~/.idun/config.toml`.
- **`idun-multi`** — the multi-provider LLM console. Talks to any of the 17
  registered providers (OpenAI, Anthropic, Groq, OpenRouter, HF, …) plus
  `race`, `cost`, `models`, `doctor`, `support`. Provider-agnostic.
  - `idun-multi wizard` configures the **default LLM provider** (picks one of
    the 17 registered providers, and **prints the provider table** so you can
    choose) in `~/.idun/config.toml`.

```text
idun-multi providers        # list providers + credential status
idun-multi -p openrouter ask "hello"   # -p goes BEFORE the subcommand
idun-multi race "explain quantum"      # compare providers on one prompt
idun-multi doctor            # environment + credential audit (also checks scripts)
idun-multi wizard            # pick the default LLM provider
idun wizard                  # configure the Azure Foundry client
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

**`idun`** — Azure AI Foundry client:

```text
idun chat "your prompt"        # one-shot completion
idun trace "your prompt"       # full agent trajectory (steps)
idun export "your prompt" -o trace.md   # run + save trajectory (json/md)
idun token                     # inspect / rotate stored Entra token
idun login                     # device-code login to your Foundry (azure/hf/openai)
idun status                    # show resolved backend + credential state
idun run <pack> <key>          # run a bundled prompt pack
idun packs                     # list bundled prompt packs
idun matrix  --docs DIR --questions FILE   # Doc x Question pivot (IDEA α)
idun diff-docs --doc-a A --doc-b B --topics T  # clause-drift compare (IDEA γ)
idun diff "A" "B"              # compare two prompt trajectories side-by-side
idun hf whoami|status|push     # Hugging Face Hub operations
idun openapi                   # print the bundled OpenAPI 3 spec for the completion API
idun logo                      # show bundled Foundry logo paths
idun welcome                   # ASCII banner
idun wizard                    # configure the Azure Foundry client
```

**`idun-multi`** — multi-provider LLM console (`-p <provider>` goes BEFORE the subcommand):

```text
idun-multi providers          # list providers + credential status
idun-multi -p openrouter ask "hello"   # chat with a provider
idun-multi race "explain quantum"      # compare providers on one prompt
idun-multi models              # list models (or --discover)
idun-multi cost                # token / cost estimate
idun-multi doctor              # environment + credential audit
idun-multi wizard              # pick the default LLM provider
```

## Supported providers

The `idun` CLI / `IdunClient` speak to any OpenAI-compatible endpoint plus the
native Azure AI Foundry transport. Registered providers (4 groups):

- **OpenAI-compatible:** `openai`, `groq`, `together`, `perplexity`, `fireworks`,
  `novita`, `xai`, `deepseek`, `mistral`, `openrouter`, `gemini`, `hf`, `nous`
- **Anthropic:** `anthropic` (Claude)
- **Azure:** `azure` (Azure AI Foundry / Idun agent)
- **Local:** `ollama`, `local` (bring your own endpoint)

> **Tested vs untested (as of 2026-08-21).** After a full audit only a subset
> of these providers has actually been exercised against a live endpoint. The
> rest are **registered and code-complete but NOT verified** — they may work,
> but nobody has confirmed it.
>
> | Status | Providers |
> |---|---|
> | ✅ tested against a live endpoint | `openrouter` (live OK), `openai` (token valid, account has no credit → HTTP 429), `hf` (migrated to `router.huggingface.co`; see note), `ollama` / `local` (correctly unreachable in CI) |
> | ⚠️ untested | `anthropic`, `groq`, `together`, `deepseek`, `mistral`, `gemini`, `xai`, `nous`, `perplexity`, `fireworks`, `novita` |
> | ℹ️ needs tenant | `azure` |
>
> See **[AUDIT-BEFEHLE.md](./AUDIT-BEFEHLE.md)** for the full command audit and
> **[BEFUNDE.md](./BEFUNDE.md)** / **[ROADMAP-FIX.md](./ROADMAP-FIX.md)** for the
> bug log. A live test harness for `idun race` is planned to exercise all
> providers before the next release.

**Hugging Face (`hf`):** migrated to the OpenAI-compatible router
`https://router.huggingface.co/v1` (the old `api-inference.huggingface.co` host
was retired and no longer resolves). Requires an HF token (`HF_TOKEN`).

Any OpenAI-compatible base URL works with zero code changes — set it in the
config and the provider switches automatically. See
**[SUPPORT_MATRIX.md](./SUPPORT_MATRIX.md)** for per-provider capability details.

## Configuration (tenant-agnostic)

`~/.idun/config.toml` (neutral defaults — supply your own resource). Secrets go
to per-provider `~/.idun/<id>.token` files (mode 0600), **not** in this file:

```toml
# Written by `idun-multi wizard` (LLM provider default):
[defaults]
provider = "openrouter"

[openrouter]
model = "deepseek/deepseek-chat"

# Written by `idun wizard` (Azure AI Foundry client):
[azure]
base   = "https://YOUR-RESOURCE.services.ai.azure.com"
agent  = "your-agent-name"
project = "your-project"
```

No tenant coordinates are baked into the shipped code. The CLI reads the config
via `idun.config`; environment variables (`IDUN_PROVIDER`, `OPENAI_API_KEY`, …)
always win over the file.

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

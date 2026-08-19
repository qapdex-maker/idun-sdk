# idun-sdk

[![PyPI](https://img.shields.io/pypi/v/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/idun-sdk.svg)](https://pypi.org/project/idun-sdk/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A thin, dependency-free Python client + CLI for **Azure AI Foundry** agents
(Idun / NatureLM). Tenant-agnostic by default: bring your own Foundry resource,
no hardcoded tenant coordinates.

- **Tenant-agnostic** — configure your own resource via `~/.idun/config.toml`
  or env vars; the SDK ships neutral defaults, never QMFI-specific values.
- **Stdlib-only core** — `urllib`, no `httpx`/`aiohttp` required.
- **Async + sync** — `IdunClient.complete()` and `AsyncIdunClient.acomplete()`.
- **Doc × Question Matrix** (IDEA α) — answer a whole document set at once.
- **Live demo, no account** — recorded trajectories at
  <https://qapdex-maker.github.io/idun-playground/>.

---

## Install

```bash
pip install idun-sdk
# with optional PDF ingest:
pip install "idun-sdk[pdf]"   # pulls PyPDF2
```

## Quick start

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
idun chat "your prompt"            # one-shot completion
idun chat --async "your prompt"   # async path
idun packs                        # list bundled prompt packs
idun run <pack> <key>             # run a bundled prompt
idun welcome                      # ASCII banner
idun wizard                       # interactive setup (always exit-able: 1-5, s, q)
idun matrix --docs DIR --questions FILE   # Doc x Question pivot (IDEA α)
```

### `idun matrix` — Idun Matrix (IDEA α)

Build an **N × M answer matrix** over documents × questions. Each cell carries
the answer, the source citation, and a status (GREEN = answered+cited,
RED = contradiction, GRAY = no info).

```bash
# 1. Put your documents in a folder (.txt / .md / .pdf)
# 2. One question per line in questions.txt
idun matrix --docs ./contracts --questions ./questions.txt
```

Output (JSON):

```json
{
  "What is the recyclate quota?": {
    "contract_a.txt": {"answer": "30% of packaging is recyclate.", "citation": "Section 4.2", "status": "GREEN"},
    "contract_b.txt": {"answer": "", "citation": "", "status": "GRAY"}
  }
}
```

Programmatic:

```python
from idun.matrix import build_matrix
from idun import IdunClient

client = IdunClient()
docs = {"a.txt": "...", "b.md": "..."}
questions = ["What is the recyclate quota?", "Is takeback offered?"]
matrix = build_matrix(client, docs, questions)
# matrix[question][doc] -> {answer, citation, status}
```

Retrieval is chunked + BM25-lite (`idun.retrieve`), document ingest handles
`.txt`/`.md` natively and `.pdf` via the optional extra (`idun.ingest`).

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

## Demo (no account needed)

- Recorded agent trajectories + the Doc × Question matrix UI:
  <https://qapdex-maker.github.io/idun-playground/>
- Matrix concept note (IDEA α/β):
  <https://github.com/qapdex-maker/idun-playground/blob/main/DOC_MATRIX_CONCEPT.md>

## Development

```bash
pip install -e ".[dev]"
pytest                 # offline; no network/API keys required
ruff check .           # lint (pinned ruff==0.15.10 in CI)
```

## License

MIT.

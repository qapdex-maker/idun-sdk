# Idun SDK - Support Matrix

Per-provider capability matrix. **Generated from the transports actually implemented in `idun/providers.py`** (via `idun.providers.support_matrix()`), so this never drifts from the code. Re-render with `idun-multi support`.

| Provider | Transport | Streaming | Tools | Vision | JSON mode |
|---|---|---|---|---|---|
| `azure` | azure | ✓ | ✓ | — | ✓ |
| `openai` | openai | ✓ | — | — | ✓ |
| `anthropic` | anthropic | — | — | — | — |
| `groq` | openai | ✓ | — | — | ✓ |
| `openrouter` | openai | ✓ | — | — | ✓ |
| `together` | openai | ✓ | — | — | ✓ |
| `deepseek` | openai | ✓ | — | — | ✓ |
| `mistral` | openai | ✓ | — | — | ✓ |
| `gemini` | openai | ✓ | — | — | ✓ |
| `xai` | openai | ✓ | — | — | ✓ |
| `nous` | openai | ✓ | — | — | ✓ |
| `hf` | hf | — | — | — | — |
| `ollama` | openai | ✓ | — | — | ✓ |
| `local` | openai | ✓ | — | — | ✓ |
| `perplexity` | openai | ✓ | — | — | ✓ |
| `fireworks` | openai | ✓ | — | — | ✓ |
| `novita` | openai | ✓ | — | — | ✓ |

## What the columns mean

- **Streaming** - true SSE token streaming (`openai` transport). Azure answers in a single chunk via the agent client; `anthropic`/`hf` fall back to a single-chunk yield so callers can still iterate.
- **Tools** - the SDK surfaces a full agent tool-trace (reasoning + tool calls). Only the Azure tool-agent does this today; other providers return a plain completion.
- **Vision** - image input wired into `complete()`. Not implemented for any provider yet.
- **JSON mode** - `response_format` / structured output accepted. Follows the same rule as `idun-multi schema` (`openai` + `azure` transports). Use `--json` on any command for the normalized shape.

## Any OpenAI-compatible endpoint

Providers using the `openai` transport (groq, openrouter, together, deepseek, mistral, gemini, xai, nous, ollama, local, perplexity, fireworks, novita) inherit the `openai` transport's capabilities: **streaming YES, JSON mode YES, tools NO, vision NO**. The wizard option `5) other` and `IDUN_<ID>_BASE` let you point any OpenAI-compatible endpoint at the same transport with zero code changes.


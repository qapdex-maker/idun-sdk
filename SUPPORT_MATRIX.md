# Idun SDK - Support Matrix

Per-provider capability matrix. **Generated from the transports actually implemented in `idun/providers.py`** (via `idun.providers.support_matrix()`), so this never drifts from the code. Re-render with `idun-multi support`.

| Provider | Transport | Streaming | Tools | Vision | JSON mode | Live-tested |
|---|---|---|---|---|---|---|
| `azure` | azure | ✓ | — | — | ✓ | ✓ |
| `openai` | openai | ✓ | ✓ | ✓ | ✓ | ✓ |
| `anthropic` | anthropic | — | ✓ | ✓ | — | ✓ |
| `groq` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `openrouter` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `together` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `deepseek` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `mistral` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `gemini` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `xai` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `nous` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `hf` | openai | ✓ | ✓ | ✓ | ✓ | ✓ |
| `ollama` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `local` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `perplexity` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `fireworks` | openai | ✓ | ✓ | ✓ | ✓ | — |
| `novita` | openai | ✓ | ✓ | ✓ | ✓ | — |

## What the columns mean

- **Streaming** - true SSE token streaming (`openai` transport). Azure answers in a single chunk via the agent client; `anthropic` falls back to a single-chunk yield so callers can still iterate. (Note: `hf` uses the `openai` transport in code, so it inherits streaming/tools/vision/json — the older "hf = hf transport, text-only" note is outdated.)
- **Tools** - function calling wired through `complete(tools=[...])` for the `openai` + `anthropic` transports. Tool calls are returned on `Completion.tool_calls` (normalized to OpenAI shape). The Azure Foundry agent tool-trace is surfaced separately via `IdunClient` (the `idun` CLI), not via `complete()`.
- **Vision** - multimodal input wired through `complete(images=[...])` for the `openai` + `anthropic` transports (image_url / image content blocks; local files are base64-encoded). `hf` inherits vision via the `openai` transport; the Azure `complete()` path is text-only.
- **JSON mode** - `response_format` / structured output accepted. Follows the same rule as `idun-multi schema` (`openai` + `azure` transports). Use `--json` on any command for the normalized shape.
- **Live-tested** - honesty flag: ✓ only when a provider was exercised against a REAL endpoint with a valid key. Code-complete (transport registered) ≠ live-tested. 3/17 currently marked ✓ (azure, openai, anthropic); the rest are wired up but unproven against a live endpoint. Flip to ✓ per-provider in `idun/providers.py` `_LIVE_TESTED` after a real call.

## Any OpenAI-compatible endpoint

Providers using the `openai` transport (groq, openrouter, together, deepseek, mistral, gemini, xai, nous, ollama, local, perplexity, fireworks, novita) inherit the `openai` transport's capabilities: **streaming YES, tools YES, vision YES, JSON mode YES**. The wizard option `5) other` and `IDUN_<ID>_BASE` let you point any OpenAI-compatible endpoint at the same transport with zero code changes.

## Using vision + tools from the CLI

```bash
idun-multi ask "What is in this chart?" --image ./chart.png
idun-multi ask "Get the weather" \
  --tools '{"type":"function","function":{"name":"get_weather",\
  "description":"weather","parameters":{"type":"object",\
  "properties":{"city":{"type":"string"}}}}}'
idun-multi ask "Get the weather" --tools ./tools.json   # JSON file
```

From Python:

```python
from idun.providers import complete
c = complete("groq", "weather?", images=["https://x/cat.png"],
              tools=[{"type": "function", "function": {
                  "name": "get_weather", "parameters": {
                      "type": "object", "properties": {"city": {"type": "string"}}}}}]
print(c.text, c.tool_calls)
```


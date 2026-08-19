# Changelog

All notable changes to the Idun SDK are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres
to semantic versioning (`MAJOR.MINOR.PATCH`).

## [1.0.15] — 2026-08-19

### Changed
- **Tenant-agnostic by default.** `idun/client.py` now resolves Foundry
  coordinates as env `IDUN_BASE/PROJECT/AGENT` > `~/.idun/config.toml`
  `[defaults] idun_base/idun_project/idun_agent` > empty. No tenant is bundled;
  every user supplies their own Azure AI Foundry resource.
- **Shipped `config.example.toml`** (neutral, placeholder-only) so the package
  is usable without any QMFI/tenant values: `cp config.example.toml
  ~/.idun/config.toml` then fill in your own resource.
- **Honest demo mode (no account needed).** The playground router and CLI fall
  back to recorded demo traces (real agent trajectories, served offline) when no
  token/resource is configured, instead of hard-crashing on "not configured".
  This keeps the tool open to non-tenant users.
- **README** updated: own resource required, demo mode documented, version
  bumped to 1.0.15.
- **MCP `serverInfo` version** now derives from `idun.__version__` (no literal),
  so it tracks automatically (was hard-coded `0.1.33`).

## [1.0.14] — 2026-08-17

### Changed
- **`idun chat` is now a live interactive session.** Running `idun chat`
  with no prompt prints an "IDUN ONLINE" console header (logo + a "console
  live" status line) and drops into a REPL — type a prompt, get the answer,
  repeat. `exit` / `quit` / `q` / Ctrl-C / EOF ends the session cleanly.
  This replaces the previous behaviour where a missing prompt just dumped the
  argparse error. `idun chat "..."` still does a single one-shot call as before.
  New `idun._cli_retro.chat_intro()` renders the live header.

## [1.0.13] — 2026-08-17

### Added
- **Cost accounting for `idun-multi race`** (last open §8 backlog item). New
  helpers in `idun.providers`:
  - `cost_table()` — approximate public list prices (USD per 1,000 input /
    output tokens) for the 12 providers with a public list price.
  - `estimate_cost(pid, prompt_tokens, completion_tokens)` — returns the
    estimated USD cost, or `None` for providers with no public list price
    (azure Foundry / NatureLM-Idun, self-hosted ollama/local, HF Inference).
  - `idun-multi race` now prints a **cost\*** column per contender; `idun-multi
    cost` prints the full table. Prices are explicitly labelled an approximation
    ("not a bill") — actual charges depend on plan, region, caching, discounts.

### Chore
- ROADMAP §8 marked fully done (all backlog items shipped across v1.0.6–v1.0.13).

## [1.0.12] — 2026-08-17

### Added
- **Vision + function calling wired through `complete()`.** New optional
  parameters `images: list[str]` and `tools: list[dict]` (plus `tool_choice`)
  on `idun.providers.complete()`. They are forwarded to the `openai` and
  `anthropic` transports:
  - **Vision** — `images` builds multimodal content blocks: OpenAI `image_url`
    blocks, Anthropic `image` blocks (base64 for local files, url for
    http(s)/data: URIs). `hf` and the Azure `complete()` path stay text-only.
  - **Tools** — `tools` enables function calling. OpenAI gets the schemas
    verbatim; Anthropic gets them converted to its `input_schema` shape. Provider
    tool calls are normalized and returned on the new `Completion.tool_calls`
    field (OpenAI shape). `_extract_tool_calls()` handles both dialects.
- **CLI** — `idun-multi ask` gains `--image` (repeatable), `--tools` (inline
  JSON or a path to a JSON file of OpenAI-style tool defs), and `--tool-choice`.
  Tool calls are rendered (and included in `--json`) on the response.
- **Tests:** `tests/test_vision_tools.py` (6 cases) verifies image-block
  building, Anthropic schema conversion, and tool_calls normalization — all
  offline via a mocked `_post_json`.
- **Docs:** `SUPPORT_MATRIX.md` regenerated; vision + tools now show ✓ for
  `openai`/`anthropic` (and the 13 openai-transport providers), azure/`complete()`
  stays text-only (its agent tool-trace is a separate `IdunClient` feature).

## [1.0.11] — 2026-08-17

### Added
- **Support matrix docs (P4 backlog item).** New `SUPPORT_MATRIX.md` documents
  per-provider capabilities (streaming / tools / vision / JSON mode). It is
  **generated from the transports actually implemented in `idun/providers.py`**
  via the new `support_matrix()` / `support_matrix_text()` helpers, so the doc
  can never drift from the code. A new `idun-multi support` command renders the
  same table live. Summary of the honest matrix:
  - **azure**: streaming ✓, tools ✓ (agent tool-trace), vision —, JSON mode ✓
  - **openai transport** (groq/openrouter/together/deepseek/mistral/gemini/xai/
    nous/ollama/local/perplexity/fireworks/novita): streaming ✓, JSON mode ✓,
    tools —, vision —
  - **anthropic / hf**: no streaming / tools / vision / JSON mode (single-chunk
    fallback)
- **Tests:** `tests/test_support_matrix.py` asserts the matrix is derived from
  the registry and matches the `cmd_schema` JSON-mode rule.

## [1.0.10] — 2026-08-17

### Added
- **Optional OS keyring backend (P4 backlog item).** New module
  `idun.keyring_store` mirrors credentials to the OS credential store (macOS
  Keychain / Windows Credential Manager / Secret Service) when opted in via
  `IDUN_KEYRING=1` or `secrets_backend = "keyring"` in config.toml **and** the
  `keyring` package is installed. It is strictly secondary: the file store
  (`~/.idun/<id>.token`, 0600) stays primary and always wins; the keyring is
  consulted only as a last-resort fallback. Zero third-party dependencies unless
  the user opts in. Every helper is non-fatal (returns `""`/`False` on any
  failure), so a missing/locked keyring never breaks resolution. Exposed in the
  public API (`idun.keyring_store`) and reported by `idun-multi doctor`
  ("secrets: file only" vs "keyring (opt-in)").
- **Tests:** `tests/test_keyring.py` (9 cases) — opt-in gating, store
  round-trip, resolve fall-through / file-precedence, save-mirror, status,
  and safe-degradation when the package is absent.

### Chore
- README Security section documents the opt-in keyring backend.

## [1.0.9] — 2026-08-17

### Fixed
- **PyPI `summary` corrected** 14→17 providers in `setup.py` long description
  (the 1.0.8 wheel shipped the registry with 17 providers but described it as
  14). No code changes; version bump only so PyPI accepts the corrected
  metadata (PyPI releases are immutable).

## [1.0.8] — 2026-08-17

### Added
- **Provider expansion (P5):** added `perplexity`, `fireworks`, and `novita` to
  the registry (all OpenAI-compatible transport). The registry now ships **17
  providers**. Each is one `Provider(...)` row — no other code changes needed.
- **`idun welcome`** documented as a pure-ASCII banner; **`idun wizard`**
  documented as always-exit-able (`1-5`, `s` skip, `q` quit).

### Changed
- **Wizard test-call is now non-alarming (P1):** a failed connection probe at
  the end of `idun wizard` prints a neutral hint instead of a red error. The
  wizard already wrote config successfully; a not-yet-live key is expected, not
  a failure.
- **README** "What's in the box" bumped to v1.0.7/1.0.8 and now lists the
  welcome banner + exit-able wizard; `setup.py` long description corrected to
  14→17 providers.
- **Neutral naming (P4):** removed the last `QMFI` reference (historical
  ROADMAP.md note); no tenant/resource is ever bundled or named in public
  artifacts.

### Chore
- **CHANGELOG.md** introduced; `ROADMAP_V2.md` marked FINAL and points here.
  (P3 — progress is now tracked in the changelog instead of the roadmap doc.)

## [1.0.7] — 2026-08-17

### Removed
- **`cmatrix` dependency entirely.** The optional matrix-rain Easter egg in
  `idun welcome` was deleted — no `subprocess`/`shutil.which` spawn, no
  `force_cmatrix` parameter, no `install_requires` entry. `idun welcome` now
  renders a pure-ASCII banner only and still leaves the shell usable via the
  hard terminal reset. This was the recurring install/runtime breaker.

### Fixed
- `tests/test_welcome.py` rewritten without any cmatrix reference.

## [1.0.6] — 2026-08-17

### Fixed
- **Broken welcome → wizard redirect.** `idun welcome` no longer auto-launches
  the interactive setup wizard (which trapped the user in a blocking prompt).
  `show_welcome_then_wizard()` was deleted; `cmd_welcome` now only renders the
  banner and points the user at `idun wizard`.

### Added
- **Wizard UX rework (`idun wizard`):**
  - `5) other` — any generic OpenAI-compatible endpoint (base URL + key + model).
  - `s` skip — keep registry defaults, only choose a theme.
  - `q` / empty / Ctrl-C / EOF — quit cleanly (rc 0, no config written).
  - TTY safety — piped/non-interactive invocation exits 1 with a clear message.

## [1.0.5] — 2026-08-17

### Changed
- Richer first-run welcome: left-aligned world-tree ASCII scene + larger
  block-letter IDUN wordmark; hard terminal reset after `cmatrix` so the shell
  is never left in a broken state.

## [1.0.0] — 2026-08 (baseline)

### Added
- 14-provider registry (OpenAI-compatible / Anthropic / Hugging Face transports).
- `idun-multi` 16-bit retro console: provider switching, credential wizard,
  model discovery, fallback chains, themes, REPL.
- Config file `~/.idun/config.toml` (env > toml > registry default).
- Structured output (`--json`, `schema`).
- Live model discovery (`GET {base}/models`, 24h cache).
- MCP server parity (`idun_chat` / `idun_trace` / `idun_export` / `idun_token`
  / `idun_providers` / `idun_ask` / `idun_race`).
- Async client (`AsyncIdunClient`, `asyncio.to_thread`).
- CI matrix (Python 3.8–3.14 + Termux/aarch64 + ruff), `py.typed`, `test.sh`
  post-install verification, security pass (getpass, 0600 tokens, error-body
  redaction, SSRF guard).

---

## Backlog (future, not blocking)

- Cost accounting: per-provider price table for `idun race`.
- Provider expansion: Perplexity, Fireworks, Novita, etc. (one `Provider()` row
  each; `5) other` already covers arbitrary OpenAI-compatible endpoints).
- OS keyring backend for credentials (optional, behind the file store).
- Support-matrix docs: streaming / tools / vision / JSON mode per provider.

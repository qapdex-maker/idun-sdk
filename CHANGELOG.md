# Changelog

All notable changes to the Idun SDK are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres
to semantic versioning (`MAJOR.MINOR.PATCH`).

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

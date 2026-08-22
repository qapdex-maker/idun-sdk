# Idun Roadmap (SDK + Playground + Docs)

Live status and forward plan for the Idun project. This document is the
planning record; release-by-release detail lives in [CHANGELOG.md](./CHANGELOG.md).

Status: **active.** Last updated 2026-08-22 (SDK 1.0.29).

---

## Status quo — shipped and live

- **idun-sdk 1.0.29** on PyPI — stdlib-only Azure AI Foundry client + CLI and
  the `idun-multi` 17-provider LLM console, plus the `idun-mcp` stdio server.
  README (badges) and `idun/openapi.json` are kept in sync with `__version__`.
- **Two CLIs, two wizards** (intentionally separate): `idun` (Azure Foundry
  client) and `idun-multi` (multi-provider console). Each has its own
  first-run wizard; both write only `~/.idun/config.toml`.
- **Tenant-agnostic by default** — Foundry coordinates come from
  `~/.idun/config.toml`; no hardcoded tenant in shipped code.
- **Idun Matrix (IDEA α)** — `idun matrix` Doc × Question pivot, tenant-agnostic.
- **Clause Drift compare (IDEA γ)** — `idun diff-docs` across topics.
- **PocketPal-style Bridge (IDEA β)** — neon PWA `matrix_app.html` + local
  `matrix_server.py` in the playground repo.
- **idun-playground** — dark Foundry look, agent-trace panel, Live/Demo badge
  via `GET /api/health`, recorded-trace demo fallback (no token/account needed).
- **Public demo (GitHub Pages)** — recorded trajectories + matrix UI, no
  backend/account: <https://qapdex-maker.github.io/idun-playground/>

### Completed capability lines (history)

- Provider registry (17 providers), 16-bit retro console, MCP server parity.
- Streaming (`--stream`), interactive REPL, fallback chains, response caching,
  retry with backoff, stdlib-only config (`~/.idun/config.toml`), structured
  output (`--json`), async client, model discovery, theme system.
- CI matrix Python 3.8–3.14 + ruff lint; `py.typed` (PEP 561); post-install
  verification (`test.sh` / `install.sh`); security pass (0600 tokens, argv-free
  secrets, SSRF guard, redacted error bodies).
- Post-v1.0: OS keyring backend (opt-in), support matrix docs
  (`SUPPORT_MATRIX.md`), vision + function calling, `idun chat` live session.

---

## Open items (not release-blocking)

1. **HF token live confirmation** — the `router.huggingface.co/v1` migration
   (B7) is verified at the code-path level; a real live `idun hf` call with a
   genuine HF token is still pending (being tested on a second device).
2. **Provider matrix honesty** — 11 of 17 providers are registered and
   code-complete but not yet exercised against a live endpoint. The public
   matrix should state tested vs untested status clearly.
3. **`idun race` test harness** — a live harness exercising all 17 providers
   before the next release (deferred by user).
4. **Codebase review tooling** — evaluate a CodeRabbit alternative. Options
   researched (2026-08-21): Qodo Merge (pr-agent, OSS, self-host), Greptile
   (SaaS, deep context), Ellipsis (YAML pipeline, self-host-in-VPC), Bito
   (SaaS, agentic), Codacy (quality+security+AI), or a self-built CLI LLM
   review. No decision yet — user choice.

---

## Forward plan

### Near term

- Resolve the HF live-test item (item 1) once the second-device test reports back.
- Make the provider support matrix honest (item 2): label tested vs untested.
- Pick a codebase-review approach (item 4).

### Mid term

- `idun race` live harness across all 17 providers (item 3).
- SSE streaming in the playground instead of poll.
- Trace export as JSON/Markdown and side-by-side trace diff (UI).

### Vision

- Idun as a backend inside the Hermes WebUI preview.
- A reusable tool-agent visualization component for other Foundry agents.
- Mobile app (PocketPal-hybrid) building on IDEA α + β.

---

## Risk register

| Risk | Mitigation |
|---|---|
| Console-script name `idun` is generic and gets hijacked | `doctor` check + `test.sh` asserts scripts resolve to this package |
| Provider model slugs rot | live model discovery |
| Hardcoded Azure resource in registry default | resolved (tenant-agnostic by default) |
| API keys in plaintext under `~/.idun` | 0600 (atomic) |
| API key leaks via argv / process table | `getpass` only |
| Rate limits during `race` | backoff + cache |
| Secrets in provider error bodies | redaction |
| `file://` SSRF via malicious `IDUN_*_BASE` | `_require_http_url` guard |

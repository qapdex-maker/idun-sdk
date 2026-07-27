# Idun Roadmap

Status quo, nahe, mittelfristige und Vision-Ziele für das Idun-Projekt
(SDK + Playground + Docs + Quality-Gate).

## Status quo (erledigt, live auf GitHub / PyPI)

- **idun-sdk** `v0.1.12` auf PyPI: `pip install idun-sdk` (stdlib-only,
  `install_requires=[]`). Client + CLI (`idun login|chat|trace|export|
  packs|run|diff|token|logo`), Entra Device-Code-Auth, Token-Auto-Rotation,
  Async (`--async`), Trace-Export, Contoso-Prompt-Packs, Side-by-Side-Diff.
- **idun-playground**: Dark-Mode (ai.azure.com-Look), Agent-Trace-Panel,
  `diff.html` (Side-by-Side-Spalten), `router.py` (stdlib HTTP-Server mit
  `/api/chat`, `/api/chat/stream` SSE, `/api/diff`). Live im Edge-Recording
  bestätigt.
- **Docs**: README/long_description (QMFI entfernt, „no admin needed"),
  Microsoft-Learn-Stil in beiden Repos.
- **CI**: `pytest`-Suite (14 passed) + GitHub Actions, offline.
- **CodeRabbit-Key verifiziert**: `cr-ce37...` ist gültig (Server akzeptiert
  ihn, `403` statt `401` am Enterprise-only Metrics-Endpoint). Pro+-Plan →
  GitHub-App PR-Review-Flow nutzbar; REST-API sonst Enterprise-gated.

## Phase 2 — Nächste Schritte (ALLE ERLEDIGT)

1. **MCP-Server-Wrapper (2.1)** — `idun_mcp.py` exponiert
   `IdunClient.complete()` als stdlib-MCP-Tool. ✓
2. **Async (2.2)** — `complete_async` via `asyncio.run_in_executor`,
   CLI `--async`. ✓
3. **Test-Suite + CI (2.3)** — `pytest` (14 passed), GitHub Actions offline. ✓
4. **PyPI-Publish (2.4)** — `v0.1.12` live, stdlib-only. ✓
5. **Token-Auto-Rotation (2.5)** — `idun login` speichert Refresh-Context,
   CLI erneuert `FOUNDRY_TOKEN` vor Ablauf. ✓
6. **Contoso-Prompt-Packs (2.6)** — `idun data/prompt_packs/contoso_pack.json`,
   `idun packs` / `idun run contoso <key>`. ✓

## Phase 3 — Mittelfristig

1. **PR #4249** bei Microsoft Learn (NatureLM-Idun-5-MoE Connector,
   independent publisher) — **EXTERN BLOCKIERT**, wartet auf Review.
2. **365-Kalendereintrag** — **EXTERN BLOCKIERT** (Exchange-Lizenz fehlt,
   Graph Device-Code bereit, 401 = keine Mailbox).
3. **Trace-Export (3.3)** — `idun export --format json|md`,
   `IdunResult.to_json()/to_markdown()`. ✓ (offline getestet)
4. **Side-by-Side-Trace (3.4)** — `idun diff`, `diff_traces()/format_diff()`,
   `diff.html` Spalten-UI. ✓ (UI + Router-Route gebaut; **Live-Test offen**,
   localhost offline)

## Phase 4 — Vision

1. **Idun als Backend in Hermes WebUI-Preview** einhängen.
2. **Wiederverwendbare Tool-Agent-Visualisierung** (Komponente) für andere
   Foundry-Agents.
3. **Streaming (SSE) (4.3)** — `router.py /api/chat/stream` (NDJSON) +
   `playground.html` `streamPrompt()`. ✓ (UI + Router gebaut; **Live-Test
   offen**, localhost offline)

## Phase 5 — Quality Gate (neu, nach CodeRabbit-Key-Test)

1. **`coderabbit.yaml`** in `idun-sdk` + `idun-playground`:
   - Severity-Threshold `critical` (Block-on-Critical, NVIDIA-Policy).
   - `ignore` für stdlib-Only-False-Positives („use requests/httpx").
   - Reviews nur auf geänderte Dateien (diff-scoped).
2. **PR-scoped Reviews (Flow 1)**: echte Änderungs-PRs öffnen, CodeRabbit
   reviewt über GitHub-App (Pro+). Findings abarbeiten.
3. **MCP-Context**: bereits alle MCPs auf CodeRabbit verifiziert — für
   Reviews einbinden (User-guidance: Idun = stdlib Foundry-Tool-Agent).

## Nächste unblockierte Schritte (Priorität)

- **A** — Phase 5 Quality Gate: `coderabbit.yaml` + erster Review-PR
  (router.py / auth.py) → CodeRabbit diff-scoped Review.
- **B** — Phase 4.1: Idun-Backend in Hermes WebUI-Preview.
- **C** — Warten auf localhost (Router E2E-Test für 3.4 / 4.3).
- **D** — Extern: PR #4249 / 365-Kalender (blockiert, nur Nachfassen).

# Idun Roadmap

Status quo, nahe, mittelfristige und Vision-Ziele für das Idun-Projekt
(SDK + Playground + Docs + Quality-Gate + WebUI).

## Status quo (erledigt, live auf GitHub / PyPI)

- **idun-sdk** `v0.1.17` auf PyPI: `pip install idun-sdk` (stdlib-only,
  `install_requires=[]`). Client + CLI (`idun login|chat|trace|export|
  packs|run|diff|token|logo`), Entra Device-Code-Auth, Token-Auto-Rotation,
  Async (`--async`), Trace-Export, Contoso-Prompt-Packs, Side-by-Side-Diff.
- **idun-playground**: Dark-Mode (ai.azure.com-Look), Agent-Trace-Panel,
  `diff.html` (Side-by-Side-Spalten), `router.py` (stdlib HTTP-Server mit
  `/api/chat`, `/api/chat/stream` SSE, `/api/diff`). **Router E2E verifiziert**
  (alle 3 Endpunkte 200 mit echtem FOUNDRY_TOKEN, live im Recording bestätigt).
- **CodeRabbit PR #1** gemergt: `router.py` Security-Hardening
  (Security-Header all-paths via `end_headers()` override, exakte Host-Check
  + loopback-bind, BrokenPipe-Abwehr). Findings F1/F2 behoben + re-verifiziert.
- **Docs**: README/long_description (QMFI entfernt, "no admin needed"),
  Sentry-MCP-Sektion (remote `https://mcp.sentry.dev/mcp` + `mcp-remote`
  OAuth-Flow), `.mcp.example.json` (idun + idun-docs + sentry Combo).
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
4. **PyPI-Publish (2.4)** — `v0.1.17` live, stdlib-only. ✓
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
   `diff.html` Spalten-UI. ✓ (UI + Router-Route + **Live-Test verifiziert**,
   Router E2E localhost 200).

## Phase 4 — Vision

1. **Idun als Backend in Hermes WebUI (4.1)** — **NICHT GEPLANT (bewusst verzichtet):**
   Entscheidung: Idun braucht keine WebUI-Integration. Die saubere, wartbare
   Anbindung ist (1) Idun als **MCP-Server** (`idun` + `idun-docs`) → Hermes
   core ruft es via Tool, und (2) der **eigenständige Playground**
   (`idun-playground`, dark Foundry-Look, Chat/Diff/SSE). Ein zweiter UI-Ort
   im fremden `hermes-webui`-Repo (AGENTS.md: 1 PR = 1 Änderung, eigene
   `.venv`-Policy, Upstream-Review) wäre Doppelpflege + Merge-Risiko bei
   Upstream-Updates, ohne echten Mehrwert.
   **PoC (lokaler Fork `~/repo/own/hermes-webui`, Branch `feat/idun-phase4-1`):**
   Tab + Chat live verifiziert — dient nur als Referenz, wird NICHT verfolgt
   und NICHT nach GitHub gepusht. HTTPS-Verbindung/Upstream-Commits: keiner.
2. **Wiederverwendbare Tool-Agent-Visualisierung (4.2)** — **ERLEDIGT:**
   `trace-viz.js` + `trace-viz.css` (stdlib ES, keine Deps) rendern eine
   Agent-Trajectory (reasoning + tool steps) in beliebige Container und nutzen
   die CSS-Variablen der Host-Seite (Foundry dark/light). `TraceViz.render()`
   (single trace) + `TraceViz.renderDiff()` (Side-by-Side mit Shared/Unique-
   Markern). `playground.html` und `diff.html` nutzen jetzt BEIDE diese eine
   Komponente (duplizierter Inline-Code entfernt). `trace-viz-demo.html`
   zeigt die Einbindung für **andere Foundry-Agents**. Node-Syntax- + Logik-
   Test grün. Committet (`74dadf6`, IN SYNC).
3. **Streaming (SSE) (4.3)** — `router.py /api/chat/stream` (NDJSON) +
   `playground.html` `streamPrompt()`. ✓ (UI + Router gebaut; **Live-Test
   verifiziert**, Router E2E localhost 200).

## Phase 5 — Quality Gate (ERLEDIGT)

1. **`coderabbit.yaml`** in `idun-sdk` + `idun-playground`:
   - Severity-Threshold `critical` (Block-on-Critical, NVIDIA-Policy).
   - `ignore` für stdlib-Only-False-Positives ("use requests/httpx").
   - Reviews nur auf geänderte Dateien (diff-scoped).
2. **PR-scoped Reviews (Flow 1)**: PR #1 (router.py) → CodeRabbit
   diff-scoped Review, Findings F1/F2 behoben, **gemergt**.
3. **MCP-Context**: alle MCPs auf CodeRabbit verifiziert — für Reviews
   einbinden (User-guidance: Idun = stdlib Foundry-Tool-Agent).
4. **Sentry MCP (Option A)**: als Provider in README + `.mcp.example.json`
   dokumentiert (remote `mcp.sentry.dev/mcp` + `mcp-remote` OAuth). SDK
   bleibt stdlib-only (kein `sentry_sdk`-Import).

## Nächste unblockierte Schritte (Priorität)

- **A / A'** — Phase 4.1 WebUI: **NICHT GEPLANT.** Bewusst verzichtet —
  Integration läuft via MCP (`idun`/`idun-docs`) + eigenständigem Playground.
  Kein WebUI-Code auf GitHub, PoC nur lokal als Referenz.
- **B** — Phase 4.2: Tool-Agent-Visualisierung als wiederverwendbare
  Komponente (`trace-viz.js`/`.css`, in playground + diff genutzt). ✓ ERLEDIGT.
- **C** — Extern: PR #4249 / 365-Kalender (blockiert, nur Nachfassen).
- **D** — Optional: Diff-Endpoint Performance (parallel Calls / SSE-Streaming
  für Diff) wenn Foundry-Latenz ein Problem wird.

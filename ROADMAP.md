# Idun Roadmap

Status quo, nahe, mittelfristige und Vision-Ziele für das Idun-Projekt
(SDK + Playground + Docs + Quality-Gate + WebUI).

## Status quo (erledigt, live auf GitHub / PyPI)

- **idun-sdk** `v0.1.18` auf PyPI (`pip install idun-sdk`): Code gemergt,
  Tag `v0.1.18` pushed, **PyPI-Upload erledigt** (live:
  https://pypi.org/project/idun-sdk/0.1.18/). Stdlib-only,
  `install_requires=[]`. Client + CLI (`idun login|chat|trace|export|
  packs|run|diff|token|logo`), Entra Device-Code-Auth, Token-Auto-Rotation,
  Async (`--async`, jetzt `get_running_loop()` statt deprecated
  `get_event_loop()`), Trace-Export, Contoso-Prompt-Packs, Side-by-Side-Diff.
- **idun-playground**: Dark-Mode (ai.azure.com-Look), Agent-Trace-Panel,
  `diff.html` (Side-by-Side-Spalten), `router.py` (stdlib HTTP-Server mit
  `/api/chat`, `/api/chat/stream` SSE, `/api/diff`, **BrokenPipeError-guarded
  SSE-Loop**). **Router E2E verifiziert** (alle 3 Endpunkte 200 mit echtem
  FOUNDRY_TOKEN, live im Recording bestätigt).
- **CodeRabbit**: PR #1 (idun-sdk, async-Fix) + PR #3 (playground, SSE-guard)
  gemergt — beide 🎉 ohne actionable Findings reviewt. `.coderabbit.yaml`
  path_filters-Bug behoben (alle diff-scoped Files werden jetzt erfasst).
- **Docs**: README/long_description (QMFI entfernt, "no admin needed"),
  Sentry-MCP-Sektion (remote `https://mcp.sentry.dev/mcp` + `mcp-remote`
  OAuth-Flow), `.mcp.example.json` (idun + idun-docs + sentry Combo).
- **CI**: `pytest`-Suite (wird über `run_tests.sh` ausgeführt, cwd-gepinnt +
  Fremd-Trees via `norecursedirs`/`--ignore` ausgeschlossen — verhindert den
  vorigen 10-Min-Crash durch Chromium/Qt-Tests unter `~/storage`). 8 Tests
  grün.
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

## Phase 6 — Idun als lebendiger Tool-Agent (ERLEDIGT, v0.1.21)

Idun ist jetzt als MCP-Server im Hermes-Ökosystem registriert, nicht nur als
CLI/Playground. Damit schließt sich die Agent-zu-Agent-Schleife.

1. **`idun-mcp` als `console_scripts`-Entry-Point** (`idun_mcp:main`) — kein
   hart-codierter Pfad mehr nötig; `hermes mcp add idun --command idun-mcp`.
2. **MCP-Tool-Surface erweitert** (6 Tools, stdlib JSON-RPC): `idun_chat`,
   `idun_trace`, `idun_export` (json|md), `idun_diff` (json|md),
   `idun_packs`, `idun_run`. Deckt jetzt die Auditing-Features des SDK ab.
3. **Headless-sicher**: `main()` liest das Token nur noch nicht-blockierend aus
   der Datei (kein `maybe_refresh()` → kein interaktiver Device-Code-Login im
   Hintergrund). Abgelaufenes/fehlendes Token → sauberer "no token"-Fehler.
4. **Bei Hermes registriert**: `hermes mcp add idun` → 6/6 Tools enabled
   (`~/.hermes/profiles/microsoft/config.yaml`). Tools sind nach NEUER Session
   verfügbar.
5. **PyPI** `v0.1.21` live (Wheel + Sdist), commit `bfc45e1`.

## Evolve-Schritte A–D (2026-08-02, v0.1.22 + v0.1.23)

SDK + MCP weiter ausgebaut und **live verifiziert** (pytest 18/18 grün, PyPI
0.1.22/0.1.23 live, MCP-Tools via stdio-Wire getestet):

- **A — SDK Resilience:** `IdunClient.complete()/complete_async()` retryen jetzt
  transiente 5xx/429 mit exponential backoff (2**attempt s, max 3 Versuche).
  Beobachtet live: Foundry wirft intermittente HTTP 500 → vorher harter Abbruch,
  jetzt automatischer Retry. 401 (Token) bleibt separater Pfad (maybe_refresh).
  Tests: `test_retry_backoff_on_transient_500`, `test_retry_gives_up_after_max_attempts`,
  `test_non_retryable_400_propagates_immediately`.
- **B — Multi-turn Conversation:** neue `Conversation`-Klasse (threaded history als
  strukturierter Text-Präfix, offline-friendlich, kein Server-Session-State nötig).
  `ask()` / `ask_async()` halten `history` (role, text). Getestet via
  `test_conversation_threads_history`.
- **D — MCP `idun_token` Tool + Diff-Parallelisierung:** `idun_token` inspiziert den
  Token-State OHNE Secret (valid, expires_in_seconds, account). Router `/api/diff`
  läuft beide Completions jetzt parallel (ThreadPoolExecutor, statt sequenziell).
- **C — Live MCP-Test (Phase 6 offen, geschlossen):** `idun_chat`/`idun_trace`/
  `idun_token` über das stdio-MCP-Wire getestet → echte Foundry-Antwort
  ("Die Hauptstadt von Griechenland ist Athen."). Dabei Bug gefunden + gefixt:
  `_tool_chat`/`_tool_trace` machten `dict(IdunResult)` (dataclass, nicht iterable)
  → jetzt `res.text`/`res.steps`/`res.model` direkt (v0.1.23).

PyPI: v0.1.22 (A+B+D) + v0.1.23 (C-Bugfix) live. idun-MCP bei Hermes: 7/7 Tools
enabled (6 + idun_token). Hinweis: Hermes lädt das MCP-Binary erst nach NEUER
Session / Reload — der in-session Call nutzt ggf. noch den Cache.

Offen (unblockiert, optional):
- `idun run` Batch (mehrere Pack-Keys / ganzer Pack auf einmal).
- Strukturierter `input` als Message-Liste statt Text-Präfix (falls Foundry
  server-seitige Conversation unterstützt).
- Side-by-side-Diff als eigenes MCP-Tool (`idun_diff` existiert bereits als CLI).

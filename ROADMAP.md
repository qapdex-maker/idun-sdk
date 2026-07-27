# Idun Roadmap

Status quo, nahe, mittelfristige und Vision-Ziele für das Idun-Projekt
(SDK + Playground + Docs).

## Status quo (erledigt, live auf GitHub)

1. **idun-sdk** — Python-Client + CLI (`idun login|chat|trace`), Entra
   Device-Code-Auth, steps-Relay. E2E verifiziert (trace = 21 Schritte).
2. **idun-playground** — Dark-Mode im ai.azure.com-Look, Agent-Trace-Panel,
   Live-Telemetrie-Terminal. Live im Edge-Recording bestätigt.
3. **Docs** in beiden Repos + Microsoft-Learn-Stil (`docs/playground.md`).
4. Repos gepusht, `.gitignore` sauber, keine offenen lokalen Diffs.

## Phase 2 — Nächste Schritte (nah)

1. **MCP-Server-Wrapper (2.1)** — `idun_mcp.py` exponiert
   `IdunClient.complete()` als Tool für fremde Agents (FastMCP/`mcp`).
   SDK ist gekapselt, kein CLI-Touch nötig.
2. **Async finalisieren** — echte `asyncio`-Variante + CLI-Flag `--async`.
3. **Test-Suite** — `pytest` statt nur `test.sh`; GitHub Actions CI läuft
   `test.sh` bei jedem Push (offline).
4. **PyPI-Publish** — `pip install idun-sdk` (**live auf PyPI**:
   https://pypi.org/project/idun-sdk/ `v0.1.0`, stdlib-only, `install_requires=[]`).
   Wheel + sdist via `python -m build`, Upload via `twine upload`.
5. **Token-Auto-Rotation im CLI** — `idun login` speichert Refresh-Context,
   CLI erneuert `FOUNDRY_TOKEN` vor Ablauf (vorhandenes
   `rotate_foundry_token.sh` einbinden).
6. **Contoso-Prompt-Packs** — kuratierte Demo-Prompts als JSON ladbar.

## Phase 3 — Mittelfristig

1. **PR #4249** bei Microsoft Learn einreichen (NatureLM-Idun-5-MoE Connector,
   independent publisher) — wartet auf Review.
2. **365-Kalendereintrag** — sobald die Exchange-Lizenz nachgerüstet ist
   (Graph Device-Code liegt bereit; 401 = keine Mailbox).
3. **Trace-Export** — Agent-Trajectory als JSON/Markdown speicherbar
   (für Docs/PR-Anhänge).
4. **Side-by-Side-Trace** — zwei Prompt-Läufe nebeneinander vergleichen
   (Tool-Timeline-Diff).

## Phase 4 — Vision

1. **Idun als Backend** in die Hermes WebUI-Preview einhängen.
2. **Wiederverwendbare Tool-Agent-Visualisierung** (Komponente) für andere
   Foundry-Agents.
3. **Streaming (SSE)** im Playground statt Poll — Schritte erscheinen
   zeichengenau live.

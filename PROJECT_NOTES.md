# PROJECT_NOTES — idun-sdk (qapdex-maker/idun-sdk)

Geklont: 2026-08-27 (Stand main 4689772, "bump to 1.0.32"). Quelle der Wahrheit = GitHub,
nicht PyPI. Lokaler Klon sync (ungepusht=0).

## Architektur (zwei Tools, BEWUSST getrennt)
- `idun` = Azure AI Foundry Client (Agent, Trajectory, Doc-Matrix, Packs, HF-Hub).
- `idun-multi` = Multi-Provider-LLM-Console (17 Provider, race, cost, models, doctor).
- Setup-Wizard GETRENNT: `idun wizard` (Azure) / `idun-multi wizard` (LLM-Provider).
  KEIN einheitlicher `idun-wizard` (war früher ein Missverständnis + kaputt).
- `idun race` bleibt im Code.

## Tests (echter Run 2026-08-27)
- `python -m pytest -q` → EXIT 0, keine Failures. 13 skipped (bewusst, live-Endpoint-
  abhängige Tests). Suite grün. ~20 Testdateien in tests/.
- HARTE REGEL (User): Push zu GitHub UND PyPI-Upload NUR auf Auftrag. PyPI NIEMALS
  allein ohne gleichzeitigen idun-sdk GitHub-Push.

## Offene Punkte (aus ROADMAP.md, "Open items") — VORBEREITET + GEPUSHT 2026-08-27
1. HF token live confirmation — code-path da (B7: router.huggingface.co/v1).
   `scripts/hf_live_check.py` bereit, wartet auf echten HF-Token.
2. Provider matrix honesty — ERLEDIGT: `support_matrix()` + SUPPORT_MATRIX.md
   um "Live-tested" erweitert (3/17 ✓: azure/openai/anthropic, 14 untested). Nebenbefund:
   alte Matrix sagte `hf=hf transport` — im Code ist hf.transport='openai' (korrigiert).
   GEPUSHT (2d3dce5).
3. `idun race` test harness — ERLEDIGT: `scripts/race_smoke.py`, echter Run
   CRASHES: 0 über 17 Provider (graceful ohne Keys). GEPUSHT.
4. CodeRabbit-Alternative — `docs/code-review-options.md` bereit (Empfehlung: self-built auf
   idun-multi). User-Entscheidung ausstehend. GEPUSHT.
Detail: ~/github/repo/idun-sdk/FAHRPLAN_OFFENE_ITEMS.md

## Bekannte behobene Bugs (aus CHANGELOG/PR-Reviews, nicht neu jagen)
- B1 Console-Scripts fehlten (PEP 621) | B2 save_credential O_EXCL-Crash (atomar) |
- B3 github->openai Alias (PAT-Leak) entfernt | B4 install.sh Fake-Success -> hard fail |
- B5 hf toter Host -> router.huggingface.co/v1 | B6 Version 0.2.6 -> dynamic |
- B7 idun hf toter Host + Token-Quelle vereinheitlicht.

## Bug-Hunting-Status (2026-08-27)
- Tests grün (exit 0). Keine Regression lokal sichtbar.
- Gezielte offene Stellen für künftiges Hunting: Punkt 1 (HF live), Punkt 2 (Matrix
  honesty — welche 11 Provider untested?), Punkt 3 (race harness).
- idun-playground: reines Demo/Docs-Repo (HTML + router.py + demo_traces.py), KEINE
  pytest-Tests. Bug-Hunting dort = HTML/JS-Review, nicht Unit-Tests.
- FAHRPLAN für die 4 offenen Items (Vorbereitung bis IGNITE November):
  ~/github/repo/idun-sdk/FAHRPLAN_OFFENE_ITEMS.md

## Deploy-Regel (HART)
- Push/PyPI NUR auf "Bescheid". Lokal bauen+testen OK.
- GitHub = Wahrheit, nicht aus PyPI-Index installieren.

# PROJECT_NOTES — idun-sdk (qapdex-maker/idun-sdk)

Geklont: 2026-08-27, aktualisiert bis 2026-08-28 (Stand main 37ebaa9, Version 1.0.34).
Quelle der Wahrheit = GitHub, nicht PyPI. Lokaler Klon = Remote (0 ahead, 0 behind).

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
1. HF token live confirmation — ERLEDIGT (Live-Call 2026-08-27: whoami "Qapdex" + chat
   "bereit" via router.huggingface.co/v1). `_LIVE_TESTED['hf']=True`. GEPUSHT.
2. Provider matrix honesty — ERLEDIGT: `support_matrix()` + SUPPORT_MATRIX.md
   um "Live-tested" erweitert (3/17 ✓: azure/openai/anthropic, 14 untested). Nebenbefund:
   alte Matrix sagte `hf=hf transport` — im Code ist hf.transport='openai' (korrigiert).
   GEPUSHT (2d3dce5).
3. `idun race` test harness — ERLEDIGT: `scripts/race_smoke.py`, echter Run
   CRASHES: 0 über 17 Provider (graceful ohne Keys). GEPUSHT.
4. CodeRabbit-Alternative — ENTSCHEIDUNG: self-built. `idun-multi review <pr>` MVP
   gebaut (cmd_review). Trockenlauf gegen dotnet/skills#1036 bewiesen (hf "KEINE
   FUNDE", openai 429 graceful). GEPUSHT. Solide-Stufe offen (labels/inline/cache).
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

## dotnet/skills PR #1036 — Stand 2026-09-28 (Ignite-November-Vorbereitung)

**Wichtig, weil es die Erwartung kippt:** hier wartete niemand auf den
Maintainer. AbhitejJohn hat am 2026-08-25 `changes requested` gesetzt, zwei
konkrete Punkte: Evals pflichtig, und Doku gehört ins README/Contributing
statt in eine eigene root-Datei. Der PR ist offen, MERGEABLE, head fff9944.

Beide Punkte waren inhaltlich schon beantwortet (eval.yaml, 13 Stimuli,
`check_eval_quality.py` exit 0 "No errors"). Was fehlte, war das Ausräumen der
beiden Einwände.

**Der stärkste Hebel war nicht der Code, sondern die Verifikation.** Der Skill
behauptete "Verified on .NET 10" mit dem Zusatz, die APIs seien unverändert.
Das ist die Zeile, bei der ein Microsoft-Reviewer nachhakt. Neu gebaut und
gelaufen gegen die gepinnte Preview-SDK `11.0.100-preview.3.26207.106` auf
`net11.0`: Build succeeded, 0 Warnungen, 0 Fehler, 4 JSON-Zeilen (2 Histogramm
am `step`-Tag, Counter, Observable Gauge). Ausgeführt in einem PRoot-
Ubuntu-24.04-Gast (glibc 2.39), weil die gepinnte SDK ein glibc-Build ist und
unter Termux/Bionic nicht läuft.

**Drei eigene Fehler, alle drei vor der Veröffentlichung gefunden:**
1. "PackageReference für MetricListener fehlt" — falsch. Das Probe-Projekt
   zielte auf net10.0, dort fehlt der Typ; auf net11.0 ist er im Framework.
   Abschnitt eingebaut und wieder entfernt.
2. "Output deterministisch kaputt, 8/8 nur 194 Bytes" — das war der Messweg.
   Unter PRoot bricht stdout ab, wenn es in eine Datei umgeleitet wird. Direkt
   auf stdout: 3x exakt 4 saubere Zeilen. Der Sample war in Ordnung.
3. Der Gast liegt unter `~/ubuntu-termux-test`, nicht `~/ubuntu-termux`, und das
   SDK-Tarball fehlte nach dem Totalverlust (196 MB neu geladen).

**Was der dotnet/skills-Skill über saubere Contributions lehrt:**
- Der Maintainer hatte zweimal dasselbe gesagt und Recht: erst das Repo prüfen
  (`find plugins -type d -name 'sample*'` → leer, kein Skill hat ein sample/),
  dann ändern. Eine Behauptung aus dem Kopf ist hier falsch gewesen.
- Was in root/docs/ liegt, wird als unpassend eingestuft. Was als Skill-Content
  nützlich ist, gehört in die SKILL.md.
- `check_eval_quality.py` ist der Gate, das vor dem Push laufen muss — exit 0,
  "No errors", und die eigene Datei darf nicht in der Beanstandungsliste stehen.

**Anbindung an Item 4 (CodeRabbit-Alternative, self-built):** siehe
FAHRPLAN_OFFENE_ITEMS.md. Kernaussage dort: der beste Fund kam nicht aus dem
`idun-multi review`, sondern aus dem Nachmessen der Repo-Konventionen. Das ist
die Kandidatur für den nächsten Automatismus im Tool.

**Nächster Check:** Cronjob 226b8664c112, täglich 10:17, meldet nur bei
Bewegung. Issue #1226 (Plattform-Constraint als Doku-Beitrag) ist offen, 0
Antworten. Letzter Reviewer-Stand unverändert "changes requested" (2026-08-25).

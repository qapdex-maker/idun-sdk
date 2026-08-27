# CodeRabbit-Evaluation (ROADMAP Open #4)

Stand: 2026-08-27. Quelle der Wahrheit: `docs/code-review-options.md` (im Repo,
committet auf `main` c9b7ea5) + die Recherche in `IDUN-PROJEKTSTAND.md`
(CodeRabbit-Alternativen, 21.08.2026). Diese Datei fasst beides und liefert
die Entscheidungsvorlage.

## Ausgangsfrage

> CodeRabbit-Alternative evaluieren.

Zwei Lesarten, beide beantwortet:

1. **CodeRabbit selbst** als Review-Tool — tauglich?
2. **Eine Alternative** zu CodeRabbit (weil CodeRabbit SaaS + Daten zu Dritten
   schickt, und dieser User Datenhoheit / self-host priorisiert).

## CodeRabbit selbst — Einordnung

- SaaS-Code-Review-Github-App. Kommentiert PRs, findet Bugs/SMells, hat
  "CodeRabbit AI"-Chat. Stärken: schnell live, gute UX, viele Sprachen.
- **Harte Gegenprobe gegen diese Umgebung:** CodeRabbit ist ein gehosteter
  Dienst — der Diff und der Kontext wandern zu einem Drittanbieter. Der User
  hat mehrfach Datenhoheit / self-host / Termux als Prämisse erklärt
  (siehe `IDUN-PROJEKTSTAND.md`, "CodeRabbit-Alternativen", und die
  Wiederaufnahme vom 27.08). CodeRabbit fällt damit als Primärwahl raus, es sei
  denn der User akzeptiert einen Cloud-Dienst.
- Auf Termux allein nicht self-hostbar (kein Docker/systemd) — aber das ist
  bei CodeRabbit irrelevant, weil es ohnehin SaaS ist.

**Fazit:** CodeRabbit ist für diesen User **keine** passende Wahl, solange
Datenhoheit Priorität hat. Die Frage verschiebt sich damit auf "welche
Alternative".

## Alternativen (recherchiert, an Quellen geprüft — 21.08.2026)

| Tool | Modell | Datenhoheit | Termux-tauglich | Aufwand |
|------|--------|-------------|-----------------|---------|
| **Self-built** (idun-multi `review`) | eigene 17 Provider | 100% lokal/API | **Ja** (reines Python) | ~1 Tag MVP |
| Qodo Merge (pr-agent) | viele Backends | self-host möglich | nur mit externem Host (Docker/VM) | ~0.5–1 Tag + Host |
| Greptile | SaaS | nein (Drittpartei) | nein | gering (App) |
| Ellipsis | Self-host-in-VPC | ja (VPC) | nur mit VPC/Host | mittel |
| Bito | SaaS | nein | nein | gering |
| Codacy | SaaS/Team | nein | nein | gering |

Detail-Pro/Contra pro Tool: siehe `docs/code-review-options.md` (Self-built vs
Qodo im Detail; die anderen SaaS-Tools sind aus Datenhoheitsgründen
ausgeschieden).

## Entscheidung (im Repo bereits getroffen — c9b7ea5)

`docs/code-review-options.md` dokumentiert:

> **ENTSCHEIDUNG (2026-08-27): self-built ✅**

Begründung (aus der Datei):
- **Synergie** — idun-multi + 17 Provider + `race`/`cost`/`schema` sind
  produktionsreif; ein Reviewer ist nur diff → race → gh-comment.
- **Kontrolle** — die Review-Logik gehört dem User (kennt die typischen
  idun-Bugs: O_EXCL-Crash, Token-Leak, toter HF-Host).
- **Multi-LLM-Redundanz** — `race` über mehrere Provider fängt Halluzinationen.

**MVP ist gebaut:** `idun-multi review <pr>` (`cmd_review` in `idun_multi.py`).
Trockenlauf gegen dotnet/skills#1036 bewiesen: diff 26856 bytes → 5 chunks,
hf lieferte "KEINE FUNDE", openai 429 graceful als ERROR (kein Crash).

### Warum self-built statt Qodo

Qodo brächte einen Container-Host mit, den der User auf Termux nicht nativ
betreiben kann (kein Docker/systemd) — eine externe VM wäre nötig. Das ist
mehr Infra-Last als ein lokales Python-Skript, das die ohnehin vorhandene
idun-multi-Engine nutzt. Qodo bleibt als **Später-Option** (falls Deep-Repo-
Context / native Inline-Kommentare gebraucht werden).

## CodeRabbit-spezifisches Urteil (die eigentliche Frage)

- CodeRabbit = SaaS, Daten zu Drittpartei → **passt nicht** zur Datenhoheit-
  Prämisse dieses Users.
- Nächste Stufe unter den Alternativen wäre Qodo (self-host), aber auch das
  braucht einen Host.
- **Konsequente Antwort auf "Daten bleiben hier" + "läuft auf Termux":**
  self-built `idun-multi review` — die einzige Option ohne fremden Dienst und
  ohne Host-Zwang. CodeRabbit wird damit **nicht** eingesetzt.

## Nächste Schritte (Solide-Stufe, noch offen)

Das MVP ist da; folgende Punkte aus `docs/code-review-options.md` sind offen:
1. **Severity-Labels** via `gh pr edit` (BUG/HIGH/MEDIUM/LOW).
2. **Inline-Kommentare** an Code-Zeilen via gh REST API (nicht nur PR-Comment).
3. **Caching** der Chunk-Ergebnisse (Wiederholungsläufe billiger).
4. **Ensemble-Stabilität** — aktuell "max 3 Provider mit Credential"; bei
   nur einem verfügbaren Provider auf ein Single-LLM-Fallback zurückfallen.

## Hinweis zur Repo-Divergenz (27.08)

Lokaler Stand `a160c0a` (Provider-Verification via `idun/verification.py` +
`cmd_verify`) und Remote `c9b7ea5` (self-built `cmd_review` + `_LIVE_TESTED`-
Dict in `providers.py`) verfolgen dieselben 4 Items, mit **inkompatiblen
Implementierungen derselben Ideen**. `a160c0a` ist auf dem Remote nicht
vertreten; ein Push würde eine Linie zerstören. Stand 27.08: Push gehalten,
Divergenz beim User zur Klärung. Diese Evaluation ist unabhängig davon
konsistent mit beiden Linien (beide wollen "ehrlich + self-built").

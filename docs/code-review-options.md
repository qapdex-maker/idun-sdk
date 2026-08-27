# Code-Review-Optionen (ROADMAP Open #4) — Vergleich self-built vs Qodo

Fokus 2026-08-27: Du willst **self-built CLI (auf idun-multi)** vs **Qodo Merge**
gegenübergestellt. Andere Optionen (Greptile/Ellipsis/Bito/Codacy) sind SaaS/VPC —
fallen weg, weil du self-host/Termux priorisierst (Datenhoheit).

## Was ist schon da (echte Code-Facts, idun-sdk)
- `idun-multi`: 17 Provider, `race` (Prompt an mehrere Provider), `cost`
  (Kostenschätzung), `schema` (JSON-mode), `ask` mit tools/vision.
- KEINE review/PR-Funktion — ein self-built Reviewer muss neu dazu:
  git diff parsen, Multi-LLM-Ensemble (z.B. race über 3 Provider),
  PR-Comment via `gh` posten, severity-Labels.
- idun-multi liefert die LLM-Engine + 17 Provider + Kosten/Tools, aber kein PR-UI.

---

## Option A — Self-built CLI LLM Reviewer (idun-multi als Engine)

**Konzept:** Eigenes Skript `idun review <pr>`:
1. `gh pr diff` holen, in chunks splitten.
2. `idun-multi race` über 3 Provider (z.B. anthropic+openai+deepseek) mit
   Review-Prompt (finde Bugs/security/dead-code).
3. Ergebnisse mergen (Mehrheits-/Severity-Logik), als PR-Comment posten.
4. Optional: severity-Labels via `gh pr edit`.

### Vorteile
- **Null neue Abhängigkeit**: idun-multi + 17 Provider schon da, Kosten nur LLM-API.
- **Volle Kontrolle**: Prompt, Ensemble, Severity-Logik, Output-Format selbst.
- **Synergie**: nutzt das, was fürs Projekt eh gebaut wurde (race/cost/schema).
- **Kein SaaS**: Datenhoheit bei dir, passt zu Termux/self-host-Präferenz.
- **Multi-LLM-Redundanz**: race über Provider = robust gegen einzelne Halluzination.
- **Offline-fähig**: lokale Provider (ollama/local) nutzbar, kein Cloud-Zwang.

### Nachteile
- **Eigenbau-Aufwand**: diff-parsing, Chunking, Merge-Logik, gh-Integration —
  ~1–2 Tage für MVP, mehr für gute Severity/Labels.
- **Keine fertige PR-UI**: kein Inline-Kommentar an Code-Zeilen (nur PR-Comment),
  kein native GitHub-Review-Thread (außer man baut es).
- **Kein Deep-Repo-Context**: kein Vector-Index über das ganze Repo (wie Greptile) —
  nur was im diff steht. Bei großen Refactors schwächer.
- **Wartung**: du pflegst die Review-Logik selbst (Prompt-Drift, Provider-Änderungen).
- **Kein Auto-Label/Auto-Fix**: muss selbst gebaut werden.

### Aufwand (realistisch)
- MVP (PR-Comment mit race-Ensemble): ~1 Tag.
- Solide (severity, labels, inline-kommentare via gh API): ~3–5 Tage.
- Production (cron/CI-trigger, caching): ~1 Woche.

---

## Option B — Qodo Merge (pr-agent, OSS)

**Konzept:** Self-hostbarer PR-Agent. Hängt an GitHub-App/Webhook, versteht
Git-Diffs nativ, bietet PR-Chat-Commands (`/review`, `/describe`, `/improve`),
Auto-Labels, Auto-Describe.

### Vorteile
- **Fertig**: PR-Chat-Commands, Auto-Labels, Auto-Describe out-of-the-box.
- **Deep-Repo-Context**: nutzt Vector-Store für besseres Verständnis großer Changes.
- **Self-host**: OSS, eigene Infra (kein SaaS-Zwang, Datenhoheit).
- **Multi-Modell**: unterstützt viele LLM-Backends (auch eigene Keys).
- **CI-Integration**: GitHub-App, Webhooks, kein eigenes Scripting nötig.
- **Community/Updates**: aktives Projekt, regelmäßige Verbesserungen.

### Nachteile
- **Hosting-Aufwand**: eigener Container/Server (oder deren Cloud). Auf Termux
  allein schwer (kein Docker/systemd) — braucht externen Host (z.B. kleine VM).
- **Setup-Komplexität**: GitHub-App, Webhook-Secret, Token-Management, Config.
- **Abhängigkeit**: externes Tool in der Pipeline (wenn es down ist, kein Review).
- **Ressourcen**: Container läuft dauerhaft (Strom/Kosten für Host).
- **Weniger Kontrolle**: Prompt-Logik ist Qodos, nicht deine (anpassbar, aber nicht
  so frei wie self-built).

### Aufwand (realistisch)
- Self-host auf VM (Docker): ~2–4h Setup + Laufende Wartung.
- Konfiguration (Labels/Commands): ~1h.
- Gesamt: ~0.5–1 Tag bis lauffähig, dann wartungsarm.

---

## Vergleichstabelle

| Kriterium            | Self-built (idun-multi) | Qodo Merge (self-host) |
|----------------------|-------------------------|------------------------|
| Erste Time-to-Value  | ~1 Tag (MVP)            | ~0.5–1 Tag (Host)      |
| Laufende Wartung     | Mittel (eigene Logik)   | Gering (Container)     |
| Datenhoheit          | 100% (lokal/API)        | 100% (self-host)       |
| Deep Repo-Context    | Nein (nur diff)         | Ja (Vector-Store)      |
| PR-UI (Inline/Thread)| Nein (nur Comment)      | Ja (native)            |
| Auto-Labels/Describe | Self-built              | Fertig                 |
| Multi-LLM-Redundanz  | Ja (race)               | Ja (Backend-wahl)      |
| Neue Abhängung       | Keine (idun-multi da)   | Qodo-Container/Host    |
| Offline (ollama)     | Ja                      | Nein (Container braucht Infra) |
| Kosten               | Nur LLM-API             | Host + LLM-API         |

---

## Einschätzung

**Empfehlung: Self-built CLI auf idun-multi-Basis**, aus drei Gründen:

1. **Synergie**: idun-multi + 17 Provider + race/cost/schema sind bereits
   produktionsreif. Ein Reviewer ist nur ~1 Tag MVP (diff → race → gh comment).
   Qodo brächte einen Container-Host mit, den du auf Termux nicht nativ betreiben
   kannst (kein Docker/systemd) — du bräuchtest eine externe VM. Das ist mehr
   Infra-Last als ein lokales Skript.

2. **Kontrolle + Lernwert**: Du besitzt die Review-Logik. Bei einem SDK-Projekt
   (idun-sdk) willst du genau die Bugs finden, die du kennst (z.B. O_EXCL-Crashes,
   Token-Leaks) — ein selbstgebauter Prompt deckt das präziser ab als Qodos Generic.

3. **Multi-LLM-Redundanz**: `race` über 3 Provider ist ein eingebauter
   Qualitätshebel (Halluzinationen fallen auf), den Qodo nur über Backend-Wahl bietet.

**Wann Qodo doch besser ist:** wenn du große Refactors mit Deep-Repo-Context
brauchst (Vector-Store) oder native Inline-Kommentare/PR-Threads willst, ohne
selbst gh-API zu frickeln. Dann: Qodo auf kleiner VM self-hosten.

**Hybrid (pragmatisch):** Self-built als MVP jetzt (nutzt idun-multi, läuft auf
Termux), Qodo später, falls der Self-built an Context-Grenzen stößt. Der Self-built
ist eh nur ~1 Tag — das Risiko ist gering.

**Entscheidung:** Du sagst "self-built" oder "qodo" — dann baue/trage ich es ein.
Bei "self-built" starte ich mit MVP: `idun review <pr>` (diff → race → gh comment).

---

## ENTSCHEIDUNG (2026-08-27): self-built ✅

Du hast "self-built" gewählt. MVP gebaut: `idun-multi review <pr>` (siehe
idun_multi.py `cmd_review`). Workflow:
1. `gh pr diff <pr> --repo <owner/repo>` holen
2. diff in chunks (6000 bytes) splitten
3. race über Ensemble (anthropic, hf, deepseek, openai, gemini, mistral — die mit
   Credential, max 3) mit strengem Review-Prompt
4. merged Review als PR-Comment posten (--post) oder dry-run (default)

Echter Trockenlauf gegen dotnet/skills#1036: diff 26856 bytes, 5 chunks, hf lieferte
"KEINE FUNDE", openai 429 (leeres Guthaben, graceful als ERROR markiert, kein Crash).
MVP funktionsfähig bewiesen.

**Solide-Stufe ERLEDIGT (2026-08-27, v1.0.34):** severity-Labels (`--labels`),
inline-Kommentare via GitHub GraphQL (`--inline`), und Ergebnis-Cache
(`~/.idun/.review_cache.json`, `--no-cache` zum Deaktivieren). Siehe
`idun/review_parse.py` + `idun/review_cache.py` + `tests/test_review.py`.


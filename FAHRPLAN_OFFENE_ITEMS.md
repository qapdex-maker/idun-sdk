# FAHRPLAN — idun-sdk offene Items (Vorbereitung bis IGNITE, November)

Stand: 2026-08-27. IGNITE ist erst im November — genug Zeit, alle offenen Items
vorzubereiten. Dies ist der Vorbereitungs-Fahrplan (nicht alles braucht Live-Tokens).

Quelle der Fakten: echte Code-Reads (idun/providers.py, idun/hf_pipeline.py,
SUPPORT_MATRIX.md, pytest exit 0).

## Item 1 — HF token live confirmation (ROADMAP Open #1)
Status: LIVE BESTÄTIGT 2026-08-27. Echter Call via scripts/hf_live_check.py:
  whoami OK ("Qapdex"), chat OK ("bereit", DeepSeek-V4-Flash via router.huggingface.co/v1).
- [x] Code-Path geprüft: HF_INFERENCE = router.huggingface.co/v1, chat/completions.
- [x] `scripts/hf_live_check.py` geschrieben + mit echtem Token ausgeführt.
- [x] `_LIVE_TESTED['hf']=True` in providers.py + SUPPORT_MATRIX.md hf-Zeile ✓.
  ERLEDIGT.

## Item 2 — Provider matrix honesty (ROADMAP Open #2)
Status: SUPPORT_MATRIX.md wurde aus support_matrix() generiert (code-path).
      Hatte KEINE "live tested"-Spalte. Behoben.
VORBEREITUNG:
- [x] `support_matrix()` um `live_tested`-Feld erweitert (manuell gepflegt in
      `_LIVE_TESTED`, Default False).
- [x] `support_matrix_text()` + SUPPORT_MATRIX.md um "Live-tested" Spalte ergänzt.
      Ehrlich: 3/17 ✓ (azure, openai, anthropic), 14 untested.
- [x] Nebenbefund korrigiert: alte Matrix sagte `hf = hf transport / text-only` —
      im Code ist `hf.transport='openai'` (volle Capabilities). Matrix + Text gerendert.
- [ ] Bei echten Live-Calls: `_LIVE_TESTED` pro Provider auf True setzen.

## Item 3 — `idun race` test harness (ROADMAP Open #3)
Status: `idun race` Logik im Code. Live-Harness über alle 17 Provider.
VORBEREITUNG:
- [x] `scripts/race_smoke.py` geschrieben: ruft jeden Provider mit Dummy-Key,
      erwartet GRACEFUL handling (kein Crash). Echter Run: CRASHES: 0 über 17
      Provider. Beweist Robustheit ohne gültige Keys.
- [ ] Bei echten Keys: echtes race über live Provider (Latenz/Cost/Priority).

## Item 4 — CodeRabbit-Alternative (ROADMAP Open #4)
Status: ENTSCHEIDEN (2026-08-27): **self-built**. MVP gebaut: `idun-multi review <pr>`
(cmd_review in idun_multi.py). Trockenlauf gegen dotnet/skills#1036 bewiesen (hf
"KEINE FUNDE", openai 429 graceful als ERROR). GEPUSHT.
VORBEREITUNG (erledigt):
- [x] `docs/code-review-options.md` angelegt: Pro/Contra + detaillierter Vergleich
      self-built vs Qodo. Empfehlung self-built.
- [x] MVP `idun-multi review <pr>` implementiert (diff → race → optional gh comment).
Solide-Stufe (offen): severity-Labels, inline-Kommentare via gh API, caching.

## Reihenfolge (bis IGNITE)
1. Item 2 (Matrix honesty) — ERLEDIGT (Vorbereitung), wartet nur auf Live-Flips.
2. Item 3 (race smoke) — ERLEDIGT (Vorbereitung), CRASHES:0 bewiesen.
3. Item 1 (HF live) — ERLEDIGT (Live-Call 2026-08-27, whoami+chat OK, _LIVE_TESTED['hf']=True).
4. Item 4 (Review-Optionen) — Doc bereit, User-Entscheidung nötig.

## Harte Regeln
- Push GitHub + PyPI NUR auf Auftrag ("Bescheid"). PyPI nie allein ohne GitHub-Push.
- GitHub = Wahrheit. Tests lokal grün (pytest exit 0) vor jedem Push.
- Kein Token/Wert ins Repo / in Commits / in Chat.

# FAHRPLAN — idun-sdk offene Items (Vorbereitung bis IGNITE, November)

Stand: 2026-08-27. IGNITE ist erst im November — genug Zeit, alle offenen Items
vorzubereiten. Dies ist der Vorbereitungs-Fahrplan (nicht alles braucht Live-Tokens).

Quelle der Fakten: echte Code-Reads (idun/providers.py, idun/hf_pipeline.py,
SUPPORT_MATRIX.md, pytest exit 0).

## Item 1 — HF token live confirmation (ROADMAP Open #1)
Status: code-path verifiziert (B7). `router.huggingface.co/v1` in providers.py:267
+ hf_pipeline.py:29. Tests test_hf_endpoint.py existiert.
VORBEREITUNG (ohne Token machbar):
- [x] Code-Path geprüft: HF_INFERENCE = router.huggingface.co/v1, chat/completions.
- [x] `scripts/hf_live_check.py` geschrieben: liest HF_TOKEN, ruft `idun hf chat` +
      `hf_whoami` aus, prüft Antwort != auth-error. WARTET auf echten Token.
- [ ] Wenn Token da: Skript ausführen, Ergebnis in PROJECT_NOTES vermerken,
      ROADMAP-Item 1 auf "erledigt" setzen, `_LIVE_TESTED['hf']=True` in providers.py.

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
Status: recherchiert, KEINE Entscheidung.
VORBEREITUNG:
- [x] `docs/code-review-options.md` angelegt: Pro/Contra je Option + Empfehlung
      (self-built CLI auf idun-multi-Basis). User-Entscheidung ausstehend.

## Reihenfolge (bis IGNITE)
1. Item 2 (Matrix honesty) — ERLEDIGT (Vorbereitung), wartet nur auf Live-Flips.
2. Item 3 (race smoke) — ERLEDIGT (Vorbereitung), CRASHES:0 bewiesen.
3. Item 1 (HF live) — Skript bereit, wartet auf Token.
4. Item 4 (Review-Optionen) — Doc bereit, User-Entscheidung nötig.

## Harte Regeln
- Push GitHub + PyPI NUR auf Auftrag ("Bescheid"). PyPI nie allein ohne GitHub-Push.
- GitHub = Wahrheit. Tests lokal grün (pytest exit 0) vor jedem Push.
- Kein Token/Wert ins Repo / in Commits / in Chat.

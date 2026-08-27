#!/usr/bin/env python3
"""hf_live_check.py — Vorbereitung für ROADMAP Open #1 (HF token live confirmation).

Code-path ist verifiziert (B7): router.huggingface.co/v1 in providers.py + hf_pipeline.py.
Dieses Skript führt einen echten Live-Call aus, sobald ein HF-Token da ist.

Token-Quelle (nie ins Repo/Commit/Chat):
  export HF_TOKEN=...   (Shellblock, vor dem Lauf)
  oder ~/.idun/hf.token anlegen (chmod 600).

Läuft OHNE Token nicht (erwartet expliziten auth-error, kein Crash).
"""
import os
import sys
from idun import providers as P


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("KEIN HF_TOKEN gesetzt — Skript wartet auf echten Token.")
        print("Setze: export HF_TOKEN=...  (oder ~/.idun/hf.token anlegen)")
        return 2
    print("HF live check (router.huggingface.co/v1)...\n")
    try:
        # whoami verifiziert, dass der Token echt + gültig ist
        from idun import hf_pipeline as HF
        info = HF.hf_whoami(token)
        print("  whoami OK:", info.get("name") or info)
        # echter chat-call
        out = P.complete("hf", "Antworte mit einem Wort: bereit", max_tokens=8)
        print("  chat OK:", out)
        print("\nHF LIVE BESTÄTIGT ✅ — ROADMAP Item 1 erledigt.")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"  HF LIVE FEHLER: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

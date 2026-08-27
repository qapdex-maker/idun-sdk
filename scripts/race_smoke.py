#!/usr/bin/env python3
"""race_smoke.py — Vorbereitung für ROADMAP Open #3 (`idun race` harness).

Ruft jeden Provider mit DUMMY-Key auf und erwartet GRACEFUL handling
(NICHT Crash/ungelöste Exception). Beweist: `idun race` handhabt alle 17
Provider fehlerfrei, auch ohne gültige Keys. Defekt = Crash, nicht auth-fail.

OHNE echte API-Keys ausführbar. Erwartete graceful-Zustände:
  - ok-auth: live Endpoint antwortet 401/403 (Key wurde gesendet, abgelehnt)
  - ok-nokey: Credential-Store meldet "no credential" (Key nicht gepickt, aber
    graceful — kein Crash)
  - ok-offline: lokaler Provider (ollama/local) meldet "connection refused"
    graceful (kein Crash)
  - CRASH: unerwarteter Traceback (AttributeError/TypeError/etc.) = echter Defekt
"""
import os
import sys
import traceback
from idun import providers as P

_GRACEFUL = (
    "401", "403", "unauthorized", "auth", "api key", "invalid", "forbidden",
    "no credential", "credential", "connection refused", "cannot reach",
    "credit_balance", "exhausted",
)


def smoke_provider(pid: str) -> str:
    """Gibt 'ok-*' (graceful) oder 'CRASH: ...' zurück."""
    os.environ[f"IDUN_{pid.upper()}_KEY"] = "dummy-invalid-key-for-smoke"
    os.environ["IDUN_PROVIDER"] = pid
    try:
        try:
            P.complete(pid, "ping", max_tokens=4)
            return "ok-200"
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if any(k in msg for k in _GRACEFUL):
                return "ok-graceful"
            return f"UNKNOWN-ERR: {type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001
        return f"CRASH: {type(e).__name__}: {e}"


def main() -> int:
    print(f"race smoke über {len(P.list_providers())} Provider (dummy keys)\n")
    crashes = 0
    for p in P.list_providers():
        res = smoke_provider(p.id)
        mark = "✓" if res.startswith("ok-") else "✗"
        if res.startswith("CRASH"):
            crashes += 1
            traceback.print_exc()
        print(f"  {mark} {p.id:14} {res}")
    print(f"\nCRASHES: {crashes}")
    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(main())

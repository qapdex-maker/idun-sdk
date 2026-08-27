"""Live-verification log for the Idun provider registry.

The support matrix in ``idun.providers`` is honest about *capability* (which
transport is wired) but not about *whether a provider has actually answered a
request lately*. 11/17 providers had never been proven to work end-to-end on a
real device. This module records that fact.

State lives in a single JSON file under the Idun config dir::

    ~/.idun/.verified.json

Schema (no secrets, ever)::

    {
      "openrouter": {
        "state": "ok",            # ok | fail | skipped | unknown
        "model": "meta-llama/...",
        "ts": 1693000000.0,       # epoch seconds of the last check
        "error": null,            # short redacted error text on failure
        "latency_ms": 412
      },
      ...
    }

Nothing here is a credential. ``error`` is passed through
``providers._sanitize_error_body`` so keys never leak. The log is purely a
local, offline-friendly cache of "did we actually call this provider" — it is
never sent anywhere and never read back by ``complete()``.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from . import providers as P

VERIFIED_FILE = os.path.join(P.CONFIG_DIR, ".verified.json")

# States a provider can be in.
OK = "ok"
FAIL = "fail"
SKIPPED = "skipped"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class VerifyRecord:
    state: str
    model: str = ""
    ts: float = 0.0
    error: str | None = None
    latency_ms: int | None = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "model": self.model,
            "ts": self.ts,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VerifyRecord":
        return cls(
            state=d.get("state", UNKNOWN),
            model=d.get("model", ""),
            ts=float(d.get("ts", 0) or 0),
            error=d.get("error"),
            latency_ms=d.get("latency_ms"),
        )


def _load() -> dict[str, dict]:
    try:
        with open(VERIFIED_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def _save(data: dict[str, dict]) -> None:
    os.makedirs(P.CONFIG_DIR, exist_ok=True)
    tmp = VERIFIED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, VERIFIED_FILE)
    try:
        os.chmod(VERIFIED_FILE, 0o600)
    except OSError:
        pass


def record(pid: str, rec: VerifyRecord) -> None:
    """Persist one provider's verification result."""
    data = _load()
    data[pid] = rec.to_dict()
    _save(data)


def state(pid: str) -> VerifyRecord:
    """Return the last recorded verification state for a provider.

    Falls back to ``unknown`` when nothing has been recorded yet.
    """
    data = _load()
    if pid in data:
        return VerifyRecord.from_dict(data[pid])
    return VerifyRecord(state=UNKNOWN)


def all_states() -> dict[str, VerifyRecord]:
    """Return every recorded verification state keyed by provider id."""
    return {pid: VerifyRecord.from_dict(d) for pid, d in _load().items()}


def clear(pid: str | None = None) -> None:
    """Forget recorded verification state (one provider, or all)."""
    if pid is None:
        if os.path.exists(VERIFIED_FILE):
            os.remove(VERIFIED_FILE)
        return
    data = _load()
    data.pop(pid, None)
    _save(data)


def is_live_ok(pid: str) -> bool:
    """True only if the provider's last recorded check succeeded."""
    return state(pid).state == OK


def run_checks(providers: list[P.Provider] | None = None, *,
               prompt: str = "Say the single word: ok",
               max_tokens: int = 8, timeout: int = 30,
               on_result=None) -> dict[str, VerifyRecord]:
    """Actually call each provider and record the outcome.

    Offline-safe: a provider with no usable credential is recorded as
    ``skipped`` (never ``fail``), so an unconfigured machine reports an honest
    "not checked" rather than a stack of false failures. A provider that raises
    ``RuntimeError`` (missing creds) is skipped; any transport error is a
    ``fail`` with a redacted message. Network access is required for the calls
    themselves — there is no mock path, this is the live smoke test.

    ``on_result`` (optional callable ``(pid, VerifyRecord) -> None``) is
    invoked after each provider so the CLI can print progressively.

    Returns the map of provider id -> VerifyRecord (also persisted to disk).
    """
    import urllib.error

    targets = providers if providers is not None else list(P.list_providers())
    results: dict[str, VerifyRecord] = {}
    for p in targets:
        # Skip providers we cannot possibly call (no credential).
        if p.needs_key and P.credential_status(p) == "none":
            rec = VerifyRecord(state=SKIPPED,
                               error="no credential configured")
            record(p.id, rec)
            results[p.id] = rec
            if on_result:
                on_result(p.id, rec)
            continue
        try:
            t0 = time.time()
            comp = P.complete(p.id, prompt, max_tokens=max_tokens,
                              timeout=timeout, no_cache=True)
            # complete() returns a Completion when stream=False (the default);
            # tell the type checker so .model is available.
            from typing import cast
            comp = cast("P.Completion", comp)
            dt_ms = int((time.time() - t0) * 1000)
            rec = VerifyRecord(state=OK, model=comp.model,
                               ts=time.time(), latency_ms=dt_ms)
        except (RuntimeError, ValueError) as e:
            # RuntimeError = missing creds / transport failure; ValueError =
            # unknown provider (shouldn't happen here). Treat as a real failure
            # only when a credential exists; otherwise skip.
            if p.needs_key and P.credential_status(p) == "none":
                rec = VerifyRecord(state=SKIPPED,
                                   error="no credential configured")
            else:
                rec = VerifyRecord(state=FAIL,
                                   error=P._sanitize_error_body(str(e))[:200],
                                   ts=time.time())
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            rec = VerifyRecord(state=FAIL,
                               error=P._sanitize_error_body(str(e))[:200],
                               ts=time.time())
        record(p.id, rec)
        results[p.id] = rec
        if on_result:
            on_result(p.id, rec)
    return results

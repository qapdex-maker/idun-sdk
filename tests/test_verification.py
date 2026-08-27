"""Tests for the live-verification log + support-matrix honesty.

These run OFFLINE: ``verification.run_checks`` is exercised with a monkeypatched
``idun.providers.complete`` so no network call is made. The point is to prove
the verification bookkeeping is correct (skip-without-credential, record-ok,
record-fail, persist-to-disk, feed the support matrix) — not to prove the
providers themselves answer, which is what `idun-multi verify` does live.
"""
import json

import idun.providers as P
from idun import verification as V


def test_matrix_now_carries_verified_columns():
    rows = P.support_matrix()
    assert rows, "matrix must be non-empty"
    for r in rows:
        assert "declared_verified" in r
        assert "live_state" in r
        assert r["live_state"] in (V.OK, V.FAIL, V.SKIPPED, V.UNKNOWN)


def test_support_text_has_declared_and_live_columns():
    txt = P.support_matrix_text()
    assert "| Declared |" in txt
    assert "| Live |" in txt
    assert "openai" in txt


def test_declared_verified_flags_present_for_tested_providers():
    rows = {r["id"]: r for r in P.support_matrix()}
    # openai / openrouter / hf were live-confirmed on a real device
    assert rows["openai"]["declared_verified"] is True
    assert rows["openrouter"]["declared_verified"] is True
    assert rows["hf"]["declared_verified"] is True
    # the rest are unproven declarations
    assert rows["groq"]["declared_verified"] is False


def test_run_checks_skips_unconfigured_provider(monkeypatch, tmp_path):
    # point the verification log at an isolated dir
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(V, "VERIFIED_FILE",
                        str(tmp_path / ".verified.json"))

    # groq has no credential in this env -> must be skipped, never failed
    res = V.run_checks([P.get_provider("groq")], max_tokens=4, timeout=5)
    assert res["groq"].state == V.SKIPPED
    # log must be written
    from pathlib import Path
    assert Path(V.VERIFIED_FILE).exists()
    data = json.loads(Path(V.VERIFIED_FILE).read_text())
    assert data["groq"]["state"] == V.SKIPPED


def test_run_checks_records_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(V, "VERIFIED_FILE",
                        str(tmp_path / ".verified.json"))

    class _FakeCompletion:
        model = "fake-model"
        latency_ms = 42
        prompt_tokens = 1
        completion_tokens = 2

    # deterministic latency: 1000.0 at t0, 1000.042 at end -> 42 ms.
    # run_checks calls time.time() at least twice (start + ts), so return a
    # value that advances by 42 ms on every call.
    _t = {"v": 1000.0}
    def _fake_time():
        v = _t["v"]
        _t["v"] += 0.042
        return v
    monkeypatch.setattr(V.time, "time", _fake_time)
    monkeypatch.setattr(P, "complete", lambda *a, **k: _FakeCompletion())
    # give groq a synthetic credential so it is not skipped
    monkeypatch.setattr(P, "credential_status",
                        lambda p: "file" if p.id == "groq" else "none")

    res = V.run_checks([P.get_provider("groq")], max_tokens=4, timeout=5)
    assert res["groq"].state == V.OK
    assert res["groq"].model == "fake-model"
    assert res["groq"].latency_ms == 42

    rec = V.state("groq")
    assert rec.state == V.OK


def test_run_checks_records_fail_redacted(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(V, "VERIFIED_FILE",
                        str(tmp_path / ".verified.json"))

    def _boom(*a, **k):
        raise RuntimeError("HTTP 401: Bearer sk-SECRET123 unauthorized")

    monkeypatch.setattr(P, "complete", _boom)
    monkeypatch.setattr(P, "credential_status",
                        lambda p: "file" if p.id == "groq" else "none")

    res = V.run_checks([P.get_provider("groq")], max_tokens=4, timeout=5)
    assert res["groq"].state == V.FAIL
    # the secret must never land in the log
    assert "sk-SECRET123" not in (res["groq"].error or "")
    assert "SECRET123" not in (res["groq"].error or "")
    # mark must be present
    assert "<redacted>" in (res["groq"].error or "")


def test_clear_forgets_state(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(V, "VERIFIED_FILE",
                        str(tmp_path / ".verified.json"))
    V.record("openrouter", V.VerifyRecord(state=V.OK, model="x", ts=1.0))
    assert V.state("openrouter").state == V.OK
    V.clear("openrouter")
    assert V.state("openrouter").state == V.UNKNOWN

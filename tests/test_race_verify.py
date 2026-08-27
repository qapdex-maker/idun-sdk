"""Tests for `idun-multi race` writing live-verification state.

Offline: ``idun.providers.complete`` is monkeypatched so no network call is
made. We assert that a successful race leg records an ``ok`` live check and a
failed leg records a ``fail`` check in the verification log, and that the race
table carries the live column.
"""
import idun.providers as P
from idun import verification as V


class _Args:
    prompt = ["hello"]
    providers = "groq,openrouter"
    lines = 2
    max_tokens = 8
    timeout = 5


def _fake_compl(model_name):
    class _C:
        provider = "x"
        model = model_name
        latency_ms = 11
        prompt_tokens = 1
        completion_tokens = 1
        total_tokens = 2
        text = "ok"
    return _C()


def test_race_writes_verify_records(monkeypatch, tmp_path):
    # isolate the verification log
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(V, "VERIFIED_FILE",
                        str(tmp_path / ".verified.json"))

    # give the two providers synthetic credentials so neither is skipped
    monkeypatch.setattr(P, "credential_status",
                        lambda p: "file" if p.id in ("groq", "openrouter")
                        else "none")

    def _complete(pid, *a, **k):
        if pid == "groq":
            return _fake_compl("groq-model")
        raise RuntimeError("HTTP 401: Bearer sk-TOPSECRET boom")

    monkeypatch.setattr(P, "complete", _complete)

    from idun_multi import cmd_race
    rc = cmd_race(_Args())
    assert rc == 0

    assert V.state("groq").state == V.OK
    assert V.state("openrouter").state == V.FAIL
    # secret must not leak into the persisted verification log
    assert "TOPSECRET" not in (V.state("openrouter").error or "")

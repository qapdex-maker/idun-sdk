"""Tests for the v0.4 response cache and retry-with-backoff (offline)."""
import json
import time

import pytest

from idun import providers as P
from idun.providers import complete, cache_get, cache_put, with_retry


# --- cache ---------------------------------------------------------------

def test_cache_roundtrip(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(P, "CACHE_DIR", str(cache_dir))
    key = P._cache_key("hf", "m", "p", "s", None, 0.7, 10)
    rec = {"text": "cached", "model": "m", "provider": "hf",
           "prompt_tokens": 1, "completion_tokens": 2,
           "latency_ms": 3, "raw": {}}
    cache_put(key, rec)
    got = cache_get(key)
    assert got["text"] == "cached"
    # a second put under a different key must not collide
    assert cache_get(P._cache_key("hf", "m", "other", "s", None, 0.7, 10)) is None


def test_cache_expiry(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(P, "CACHE_DIR", str(cache_dir))
    key = P._cache_key("hf", "m", "p", "s", None, 0.7, 10)
    cache_put(key, {"text": "x", "model": "m", "provider": "hf",
                    "prompt_tokens": 0, "completion_tokens": 0,
                    "latency_ms": 0, "raw": {}})
    # expire it by rewriting the record ts into the past
    path = P._cache_path(key)
    with open(path, encoding="utf-8") as fh:
        rec = json.load(fh)
    rec["ts"] = time.time() - (P.CACHE_MAX_AGE_S + 10)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    assert cache_get(key) is None


def test_cache_hit_short_circuits_transport(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "CACHE_DIR", str(tmp_path / "cache"))
    # hermetic: don't depend on a real OPENAI_API_KEY in the env
    monkeypatch.setattr(P, "resolve_credential", lambda p: "fake-token")
    calls = {"n": 0}

    def fake_openai(p, prompt, model, token, **kw):
        calls["n"] += 1
        return {"choices": [{"message": {"content": "LIVE"}}]}

    monkeypatch.setattr(P, "_TRANSPORTS", dict(P._TRANSPORTS))
    P._TRANSPORTS["openai"] = fake_openai

    # first call populates the cache
    r1 = complete("openai", "hello", model="gpt-x", no_cache=False)
    # second identical call must be served from cache (transport not hit again)
    r2 = complete("openai", "hello", model="gpt-x", no_cache=False)
    assert r1.text == r2.text == "LIVE"
    assert calls["n"] == 1


def test_no_cache_bypasses_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "CACHE_DIR", str(tmp_path / "cache"))
    # hermetic: don't depend on a real OPENAI_API_KEY in the env
    monkeypatch.setattr(P, "resolve_credential", lambda p: "fake-token")
    calls = {"n": 0}

    def fake_openai(p, prompt, model, token, **kw):
        calls["n"] += 1
        return {"choices": [{"message": {"content": "LIVE"}}]}

    monkeypatch.setattr(P, "_TRANSPORTS", dict(P._TRANSPORTS))
    P._TRANSPORTS["openai"] = fake_openai

    complete("openai", "hi", model="gpt-x", no_cache=True)
    complete("openai", "hi", model="gpt-x", no_cache=True)
    assert calls["n"] == 2  # each call hit the transport


# --- retry ---------------------------------------------------------------

def test_with_retry_succeeds_first_try():
    assert with_retry(lambda: "ok", retries=3) == "ok"


def test_with_retry_backs_off_on_429(monkeypatch):
    import urllib.error
    sleeps = []

    def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(P.time, "sleep", fake_sleep)

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(
                "url", 429, "rate", {}, None)
        return "third time lucky"

    assert with_retry(flaky, retries=3) == "third time lucky"
    assert calls["n"] == 3
    # two backoffs happened (attempts 0 and 1), each >= 1s (base 2**attempt)
    assert len(sleeps) == 2
    assert sleeps[0] >= 1.0 and sleeps[1] >= 2.0


def test_with_retry_gives_up_on_non_retryable(monkeypatch):
    import urllib.error
    monkeypatch.setattr(P.time, "sleep", lambda s: None)

    def forbidden():
        raise urllib.error.HTTPError("url", 403, "nope", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        with_retry(forbidden, retries=3)


def test_with_retry_honors_retry_after(monkeypatch):
    import urllib.error
    import io

    def make_429(retry_after):
        headers = {"Retry-After": str(retry_after)}
        return urllib.error.HTTPError("url", 429, "r", headers, io.BytesIO(b""))

    sleeps = []
    monkeypatch.setattr(P.time, "sleep", lambda s: sleeps.append(s))

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise make_429(7.0)
        return "ok"

    assert with_retry(flaky, retries=2) == "ok"
    assert sleeps == [7.0]  # Retry-After wins over exponential base

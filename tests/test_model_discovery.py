"""Tests for v0.5 model discovery (offline, hermetic)."""

import pytest

import idun.providers as P


@pytest.fixture(autouse=True)
def _no_live(monkeypatch):
    monkeypatch.setenv("IDUN_BASE", "https://test.invalid")
    monkeypatch.setenv("IDUN_PROJECT", "test-project")
    monkeypatch.setenv("IDUN_TENANT", "00000000-0000-0000-0000-000000000000")
    # isolate the models cache dir
    import tempfile
    d = tempfile.mkdtemp()
    monkeypatch.setattr(P, "MODELS_CACHE_DIR", d)
    monkeypatch.setenv("IDUN_NO_MODELS_CACHE", "")
    yield


def test_discover_parses_openai_models_list(monkeypatch):
    fake = {"data": [
        {"id": "gpt-4o-mini"}, {"id": "gpt-4o"}, {"id": "o4-mini"}]}
    monkeypatch.setattr(P, "_get_json", lambda url, headers, timeout: fake)
    ids = P.discover_models("openai")
    assert ids == ["gpt-4o-mini", "gpt-4o", "o4-mini"]


def test_discover_falls_back_to_registry_on_error(monkeypatch):
    def boom(url, headers, timeout):
        raise RuntimeError("HTTP 401")
    monkeypatch.setattr(P, "_get_json", boom)
    p = P.get_provider("openai")
    ids = P.discover_models("openai")
    assert ids == list(p.models)


def test_discover_non_openai_returns_registry(monkeypatch):
    # anthropic has no uniform /models endpoint we rely on
    ids = P.discover_models("anthropic")
    assert ids == list(P.get_provider("anthropic").models)


def test_discover_caches_and_serves_cache(monkeypatch):
    calls = {"n": 0}

    def fake(url, headers, timeout):
        calls["n"] += 1
        return {"data": [{"id": "cached-model"}]}

    monkeypatch.setattr(P, "_get_json", fake)
    first = P.discover_models("openai")
    assert first == ["cached-model"]
    assert calls["n"] == 1
    # second call should hit cache, not re-fetch
    second = P.discover_models("openai")
    assert second == ["cached-model"]
    assert calls["n"] == 1


def test_discover_force_bypasses_cache(monkeypatch):
    calls = {"n": 0}

    def fake(url, headers, timeout):
        calls["n"] += 1
        return {"data": [{"id": f"m{calls['n']}"}]}

    monkeypatch.setattr(P, "_get_json", fake)
    P.discover_models("openai")
    P.discover_models("openai", force=True)
    assert calls["n"] == 2


def test_discover_empty_response_falls_back(monkeypatch):
    monkeypatch.setattr(P, "_get_json", lambda url, headers, timeout: {"data": []})
    p = P.get_provider("openai")
    assert P.discover_models("openai") == list(p.models)


def test_require_http_url_rejects_file_scheme():
    # _require_http_url must refuse non-http(s) before any connection is made
    with pytest.raises(ValueError):
        P._require_http_url("file:///etc/passwd")
    # https is accepted
    assert P._require_http_url("https://api.openai.com/v1/models") == \
        "https://api.openai.com/v1/models"

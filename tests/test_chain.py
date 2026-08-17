"""Tests for fallback chains (IDUN_CHAIN / complete_chain)."""
import pytest

import idun.providers as P
from idun.providers import Completion, complete_chain


@pytest.fixture(autouse=True)
def _no_live(monkeypatch):
    monkeypatch.setenv("IDUN_BASE", "https://test.invalid")
    monkeypatch.setenv("IDUN_PROJECT", "test-project")
    monkeypatch.setenv("IDUN_TENANT", "00000000-0000-0000-0000-000000000000")


def _install_router(monkeypatch, responses: dict):
    """responses: pid -> Completion or Exception. Simulate per-provider fate."""
    def fake(pid, prompt, **kw):
        r = responses.get(pid)
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise RuntimeError(f"{pid}: no credential")
        return r
    monkeypatch.setattr(P, "complete", fake)


def test_first_link_wins(monkeypatch):
    a = Completion(text="A", model="m", provider="groq")
    b = Completion(text="B", model="m", provider="openai")
    def fake(pid, prompt, **kw):
        return a if pid == "groq" else b
    monkeypatch.setattr(P, "complete", fake)
    c = complete_chain(["groq", "openai"], "hi")
    assert c.text == "A"
    assert c.raw["_served_by"] == "groq"
    assert c.raw["_chain"] == ["groq", "openai"]


def test_falls_through_to_second_link(monkeypatch):
    err = RuntimeError("groq: 429 rate limited")
    b = Completion(text="B", model="m", provider="openai")
    def fake(pid, prompt, **kw):
        if pid == "groq":
            raise err
        return b
    monkeypatch.setattr(P, "complete", fake)
    c = complete_chain(["groq", "openai"], "hi")
    assert c.text == "B"
    assert c.raw["_served_by"] == "openai"


def test_all_links_fail_raises_with_detail(monkeypatch):
    e1 = RuntimeError("groq: no credential")
    e2 = ValueError("openai: boom")
    def fake(pid, prompt, **kw):
        raise e1 if pid == "groq" else e2
    monkeypatch.setattr(P, "complete", fake)
    with pytest.raises(RuntimeError) as ei:
        complete_chain(["groq", "openai"], "hi")
    assert "all chain links failed" in str(ei.value)
    assert "groq" in str(ei.value) and "openai" in str(ei.value)


def test_chain_from_env_var(monkeypatch):
    import os
    monkeypatch.setenv("IDUN_CHAIN", "groq, openai , together")
    chain = [x.strip() for x in (os.environ.get("IDUN_CHAIN") or "").split(",") if x.strip()]
    assert chain == ["groq", "openai", "together"]
    from idun.providers import get_provider
    for pid in chain:
        assert get_provider(pid) is not None

"""Tests for the v0.5 async client (offline)."""
import asyncio

import pytest

from idun.async_client import AsyncIdunClient
from idun.providers import Completion


@pytest.fixture(autouse=True)
def _no_live(monkeypatch):
    monkeypatch.setenv("IDUN_BASE", "https://test.invalid")
    monkeypatch.setenv("IDUN_PROJECT", "test-project")
    monkeypatch.setenv("IDUN_TENANT", "00000000-0000-0000-0000-000000000000")
    state = {"calls": []}

    def fake(pid, prompt, **kw):
        state["calls"].append((pid, prompt))
        return Completion(text=f"{pid}:{prompt}", model="m", provider=pid,
                          prompt_tokens=1, completion_tokens=1, latency_ms=1)

    monkeypatch.setattr("idun.providers.complete", fake)
    return state


def test_acomplete_returns_completion(_no_live):
    c = AsyncIdunClient()
    out = asyncio.run(c.acomplete("groq", "hi"))
    assert isinstance(out, Completion)
    assert out.text == "groq:hi"


def test_acomplete_chain(_no_live):
    c = AsyncIdunClient()

    async def go():
        return await c.acomplete_chain(["groq", "openai"], "q")
    out = asyncio.run(go())
    assert out.text == "groq:q"
    assert out.raw["_served_by"] == "groq"


def test_gather_fans_out_concurrently(_no_live):
    c = AsyncIdunClient()

    async def go():
        return await c.gather(
            c.acomplete("groq", "a"),
            c.acomplete("openai", "b"),
            c.acomplete("mistral", "c"),
        )
    results = asyncio.run(go())
    texts = {r.text for r in results}
    assert texts == {"groq:a", "openai:b", "mistral:c"}


def test_active_provider_and_record(_no_live, monkeypatch):
    c = AsyncIdunClient()
    assert c.active_provider() == "azure"  # default when nothing configured
    p = c.provider("groq")
    assert p.id == "groq"
    with pytest.raises(ValueError):
        c.provider("nope")

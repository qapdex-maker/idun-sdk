"""Tests for the cfaig (Cloudflare AI Gateway) provider.

Red phase: these fail before the provider is registered. Green after the
`cloudflare` transport + `cfaig` registry entry land in providers.py.
"""
import pytest

import idun.providers as P


def test_cfaig_is_registered():
    ids = [p.id for p in P.list_providers()]
    assert "cfaig" in ids


def test_cfaig_default_model():
    p = P.get_provider("cfaig")
    assert p.default_model == "dynamic/auto"
    assert p.transport == "cloudflare"


def test_cfaig_uses_cf_aig_authorization_header(monkeypatch):
    """Cloudflare AI Gateway compat needs `cf-aig-authorization`, NOT the
    standard `Authorization` header that the openai transport sends."""
    monkeypatch.setenv("CF_AIG_TOKEN", "cf-tok")
    monkeypatch.setenv("IDUN_CFAIG_BASE",
                       "https://gateway.ai.cloudflare.com/v1/acc/gw/compat")
    seen = {}

    def fake_post(url, body, headers, timeout):
        seen["url"] = url
        seen["headers"] = headers
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(P, "_post_json", fake_post)
    c = P.complete("cfaig", "hi")
    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"].get("cf-aig-authorization") == "Bearer cf-tok"
    assert "Authorization" not in seen["headers"], \
        "cfaig must use cf-aig-authorization, not the openai Authorization header"
    assert c.text == "ok"


def test_cfaig_requires_configured_base(monkeypatch):
    """If IDUN_CFAIG_BASE is unset, the registry default still contains the
    <account>/<gateway> placeholders. Calling complete() must fail with a
    clear configuration error, NOT a cryptic Cloudflare 403/1010."""
    monkeypatch.delenv("IDUN_CFAIG_BASE", raising=False)
    monkeypatch.setenv("CF_AIG_TOKEN", "cf-tok")  # credential OK, base is the issue
    monkeypatch.setattr(P, "CONFIG_DIR", "/nonexistent-idun-dir-cfaig")
    with pytest.raises(RuntimeError, match="IDUN_CFAIG_BASE"):
        P.complete("cfaig", "hi")




"""Guard tests: no tenant-specific configuration may ship inside the package.

These lock in the fix for the audit risk "hardcoded Azure resource in the
registry default". The SDK must be usable by anyone, and must never point an
unconfigured user at somebody else's Foundry resource or Entra tenant.
"""
from __future__ import annotations

import pathlib
import re

import pytest

import idun
from idun import auth, client, providers

PKG_DIR = pathlib.Path(idun.__file__).parent
ROOT = PKG_DIR.parent

# Patterns that must never appear in shipped source.
# NOTE: assembled from fragments so this test file does not itself contain the
# literals it forbids (otherwise it would flag itself, and would ship the very
# identifiers we are removing).
_ORG = "qm" + "fi"
_TENANT_HEAD = "885f01ab" + "-7364"
_UPN_DOMAIN = "onmicrosoft" + r"\."  + "com"
FORBIDDEN = (
    re.compile(_ORG + r"[-a-z0-9]*", re.I),
    re.compile(_TENANT_HEAD + r"-[0-9a-f-]+", re.I),
    re.compile(_UPN_DOMAIN, re.I),
)


def _shipped_sources():
    files = sorted(PKG_DIR.rglob("*.py"))
    files += [ROOT / n for n in ("idun_cli.py", "idun_mcp.py", "idun_multi.py")]
    # tests ship inside the sdist, so they must stay clean too
    files += sorted((ROOT / "tests").glob("*.py"))
    return [f for f in files if f.is_file()]


@pytest.mark.parametrize("path", _shipped_sources(), ids=lambda p: p.name)
def test_no_tenant_identifiers_in_shipped_code(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    for pat in FORBIDDEN:
        assert not pat.search(text), f"{path.name} leaks {pat.pattern!r}"


def test_auth_defaults_to_multitenant(monkeypatch):
    monkeypatch.delenv("IDUN_TENANT", raising=False)
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    assert auth.tenant() == "organizations"
    assert "organizations" in auth.auth_endpoint()
    assert "885f01ab" not in auth.auth_endpoint()


def test_auth_endpoint_follows_env(monkeypatch):
    monkeypatch.setenv("IDUN_TENANT", "11111111-2222-3333-4444-555555555555")
    assert "11111111-2222-3333-4444-555555555555" in auth.auth_endpoint()


def test_auth_endpoint_resolved_at_call_time(monkeypatch):
    """Regression: the endpoint must not freeze at import time."""
    monkeypatch.setenv("IDUN_TENANT", "aaaa")
    first = auth.auth_endpoint()
    monkeypatch.setenv("IDUN_TENANT", "bbbb")
    assert auth.auth_endpoint() != first
    assert "bbbb" in auth.auth_endpoint()


def test_client_raises_when_azure_unconfigured(monkeypatch):
    monkeypatch.delenv("IDUN_BASE", raising=False)
    monkeypatch.delenv("IDUN_PROJECT", raising=False)
    with pytest.raises(ValueError, match="not configured"):
        client.IdunClient(token="x")


def test_client_reads_azure_config_from_env(monkeypatch):
    monkeypatch.setenv("IDUN_BASE", "https://mine.services.ai.azure.com/")
    monkeypatch.setenv("IDUN_PROJECT", "my-project")
    monkeypatch.setenv("IDUN_AGENT", "my-agent")
    c = client.IdunClient(token="x")
    assert c.base == "https://mine.services.ai.azure.com"
    assert c.project == "my-project"
    assert c.agent == "my-agent"
    assert "mine.services.ai.azure.com" in c._url()
    assert "my-project" in c._url()


def test_explicit_args_win_over_env(monkeypatch):
    monkeypatch.setenv("IDUN_BASE", "https://env.services.ai.azure.com")
    monkeypatch.setenv("IDUN_PROJECT", "env-project")
    c = client.IdunClient(token="x", base="https://arg.example.com",
                          project="arg-project")
    assert c.base == "https://arg.example.com"
    assert c.project == "arg-project"


def test_non_azure_backend_needs_no_azure_config(monkeypatch):
    """A user with no Azure tenant at all must still be able to use the SDK."""
    monkeypatch.delenv("IDUN_BASE", raising=False)
    monkeypatch.delenv("IDUN_PROJECT", raising=False)
    c = client.IdunClient(backend="hf", hf_token="t")
    assert c.backend == "hf"


def test_azure_provider_base_is_placeholder():
    p = providers.get_provider("azure")
    assert _ORG not in p.base.lower()
    assert "<resource>" in p.base


def test_azure_provider_base_follows_idun_base(monkeypatch):
    monkeypatch.setenv("IDUN_BASE", "https://mine.services.ai.azure.com")
    assert providers.get_provider("azure").resolved_base() == \
        "https://mine.services.ai.azure.com"

"""Pytest configuration for idun-sdk.

Keeps the suite hermetic: every test runs with `maybe_refresh()` stubbed so
no test can accidentally trigger a real Entra device-code login (which blocks
forever waiting for a browser code). The "offline" tests only ever exercise the
HTTP client via monkeypatched `_post_once`, so they must not reach live auth.

CI passed previously only by luck (no token file present -> maybe_refresh
returns None). On a machine with a stale/expired token file, the unstubbed
call would fall through to interactive `login()` and hang the run. This fixture
makes that impossible regardless of the environment.

Since v0.2.1 no Azure tenant is bundled with the package, so `IdunClient()`
raises unless IDUN_BASE/IDUN_PROJECT are configured. Tests get a synthetic,
obviously-fake resource injected here — never a real tenant.
"""
import idun.auth
import pytest

# Deliberately non-existent resource: any accidental live call must fail fast.
FAKE_BASE = "https://test-resource.services.ai.azure.com"
FAKE_PROJECT = "test-project"
FAKE_TENANT = "00000000-0000-0000-0000-000000000000"


@pytest.fixture(autouse=True)
def _no_live_auth(monkeypatch):
    """Stub maybe_refresh() so tests never perform real token rotation/login."""
    monkeypatch.setattr(idun.auth, "maybe_refresh", lambda *args, **kwargs: None)
    yield


@pytest.fixture(autouse=True)
def _fake_azure_config(monkeypatch):
    """Provide a synthetic Azure Foundry config for the whole suite.

    Guarantees no test depends on a real tenant, and that a missing local
    environment cannot make the suite pass or fail by accident.
    """
    monkeypatch.setenv("IDUN_BASE", FAKE_BASE)
    monkeypatch.setenv("IDUN_PROJECT", FAKE_PROJECT)
    monkeypatch.setenv("IDUN_TENANT", FAKE_TENANT)
    yield


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path_factory):
    """Route the response cache to a per-session temp dir.

    Since v0.4 ``complete()`` caches under ``~/.idun/cache``. Without this
    fixture a prior run (or an interactive call) could leave a real cache
    entry that a later test would wrongly serve as a hit — masking transport
    mocks. Pointing CACHE_DIR at a fresh temp dir keeps every test hermetic.
    Tests that explicitly exercise caching patch CACHE_DIR themselves.
    """
    import idun.providers as P
    monkeypatch.setattr(P, "CACHE_DIR", str(tmp_path_factory.mktemp("idun-cache")))
    yield

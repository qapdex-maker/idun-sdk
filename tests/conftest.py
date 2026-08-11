"""Pytest configuration for idun-sdk.

Keeps the suite hermetic: every test runs with `maybe_refresh()` stubbed so
no test can accidentally trigger a real Entra device-code login (which blocks
forever waiting for a browser code). The "offline" tests only ever exercise the
HTTP client via monkeypatched `_post_once`, so they must not reach live auth.

CI passed previously only by luck (no token file present -> maybe_refresh
returns None). On a machine with a stale/expired token file, the unstubbed
call would fall through to interactive `login()` and hang the run. This fixture
makes that impossible regardless of the environment.
"""
import idun.auth
import pytest


@pytest.fixture(autouse=True)
def _no_live_auth(monkeypatch):
    """Stub maybe_refresh() so tests never perform real token rotation/login."""
    monkeypatch.setattr(idun.auth, "maybe_refresh", lambda *args, **kwargs: None)
    yield

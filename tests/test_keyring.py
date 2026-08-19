"""Offline tests for the optional OS keyring backend (idun.keyring_store).

The keyring package is NOT a dependency, so these tests exercise the module
purely through monkeypatching — no real keyring install required. They cover:

1. Opt-in gating: disabled by default, enabled via IDUN_KEYRING=1 or config
   `secrets_backend = "keyring"`; never enabled when the package is absent.
2. Read/write/delete against a faked keyring backend.
3. Integration: resolve_credential falls through to the keyring only when the
   file/env/config stores are empty and the keyring is opted in.
4. Non-fatality: every helper returns "" / False / "file only" safely when the
   keyring import fails.
"""
import os
import sys

import idun.keyring_store as kr
import idun.providers as P
from idun.providers import get_provider


# A tiny in-memory fake that mimics the `keyring` module surface we use.
class _FakeKeyring:
    def __init__(self):
        self._store = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


def _install_fake(monkeypatch):
    """Make `import keyring` resolve to a fake, and force opt-in on."""
    fake = _FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setenv("IDUN_KEYRING", "1")
    return fake


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("IDUN_KEYRING", raising=False)
    # ensure config does not opt in either
    monkeypatch.setattr(kr, "_config_opt_in", lambda: False)
    assert kr.keyring_enabled() is False


def test_enabled_via_env(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setenv("IDUN_KEYRING", "1")
    assert kr.keyring_enabled() is True


def test_enabled_via_config(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.delenv("IDUN_KEYRING", raising=False)
    monkeypatch.setattr(kr, "_config_opt_in", lambda: True)
    assert kr.keyring_enabled() is True


def test_store_roundtrip(monkeypatch):
    _install_fake(monkeypatch)
    p = get_provider("groq")
    assert kr.store_keyring(p, "sk-fake123") is True
    assert kr.load_keyring(p) == "sk-fake123"
    assert kr.keyring_status(p) == "keyring"
    assert kr.delete_keyring(p) is True
    assert kr.load_keyring(p) == ""
    assert kr.keyring_status(p) == ""


def test_resolve_falls_through_to_keyring(monkeypatch, tmp_path):
    """resolve_credential reads the keyring only when file/env/config are empty."""
    fake = _install_fake(monkeypatch)
    p = get_provider("groq")

    # remove any on-disk token file so file store is empty
    if os.path.exists(p.token_file):
        os.remove(p.token_file)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    # pre-seed the keyring
    fake.set_password(kr.SERVICE_NAME, "groq", "sk-from-keyring")

    resolved = P.resolve_credential(p)
    assert resolved == "sk-from-keyring", "must fall through to keyring when empty"


def test_resolve_prefers_file_over_keyring(monkeypatch, tmp_path):
    """The file store must win over the keyring (file is primary)."""
    fake = _install_fake(monkeypatch)
    p = get_provider("groq")
    if os.path.exists(p.token_file):
        os.remove(p.token_file)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    fake.set_password(kr.SERVICE_NAME, "groq", "«redacted:sk-…»")
    # write a token file (0600) — this should take precedence
    os.makedirs(os.path.dirname(p.token_file), exist_ok=True)
    with open(p.token_file, "w", encoding="utf-8") as fh:
        fh.write("sk-from-file")
    os.chmod(p.token_file, 0o600)

    try:
        assert P.resolve_credential(p) == "sk-from-file"
    finally:
        if os.path.exists(p.token_file):
            os.remove(p.token_file)


def test_save_mirrors_to_keyring(monkeypatch):
    fake = _install_fake(monkeypatch)
    p = get_provider("groq")
    if os.path.exists(p.token_file):
        os.remove(p.token_file)
    try:
        P.save_credential(p, "sk-mirror-me")
        assert fake.get_password(kr.SERVICE_NAME, "groq") == "sk-mirror-me"
    finally:
        if os.path.exists(p.token_file):
            os.remove(p.token_file)


def test_status_reports_keyring(monkeypatch):
    fake = _install_fake(monkeypatch)
    p = get_provider("groq")
    if os.path.exists(p.token_file):
        os.remove(p.token_file)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    fake.set_password(kr.SERVICE_NAME, "groq", "sk-x")
    try:
        assert P.credential_status(p) == "keyring"
    finally:
        if os.path.exists(p.token_file):
            os.remove(p.token_file)


def test_keyring_absent_is_safe(monkeypatch):
    """When the keyring package truly can't be imported, everything degrades."""
    monkeypatch.delenv("IDUN_KEYRING", raising=False)
    monkeypatch.setattr(kr, "_config_opt_in", lambda: False)
    monkeypatch.setitem(sys.modules, "keyring", None)  # import will fail
    p = get_provider("groq")
    assert kr.keyring_enabled() is False
    assert kr.load_keyring(p) == ""
    assert kr.store_keyring(p, "x") is False
    assert kr.delete_keyring(p) is True
    assert kr.keyring_status(p) == ""

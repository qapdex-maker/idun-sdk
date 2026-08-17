"""Optional OS keyring backend for Idun SDK credentials.

This is an *opt-in, secondary* secret store. The file store under
``~/.idun/<id>.token`` (0600) remains the primary, dependency-free default and
always wins when present. The keyring is used only when:

  * the ``keyring`` package is importable, AND
  * the user opts in via ``IDUN_KEYRING=1`` (env) or
    ``secrets_backend = "keyring"`` in ``~/.idun/config.toml``, AND
  * there is no env key and no token file for the provider.

When active, secrets are written to the OS credential store (macOS Keychain,
Windows Credential Manager, Secret Service on Linux via SecretStorage, or the
Termux/Android fallback when ``keyrings.alt`` is installed) under the service
name ``idun-sdk`` with the provider id as the username.

Design rules (consistent with the rest of the SDK):
  * stdlib-only at import time — ``keyring`` is imported lazily inside the
    helpers, so the SDK keeps running headless on Termux/Android with no
    third-party dependency unless the user explicitly installs ``keyring``.
  * never raises: every helper returns ``None`` / ``""`` on any failure
    (missing package, backend locked, unsupported platform) so the caller
    silently falls back to the next store.
  * no secrets are ever printed; status reporting is secret-free.

Public API:
    keyring_enabled()        -> bool  (opt-in active AND package importable)
    load_keyring(p)          -> str   (token or "")
    store_keyring(p, token)  -> bool  (True on success)
    delete_keyring(p)        -> bool  (True if removed / already absent)
    keyring_status(p)        -> str   ("keyring" / "" )
"""
from __future__ import annotations

import os

# service name used for every provider entry in the OS keyring
SERVICE_NAME = "idun-sdk"

# env switch + config key that turn the keyring backend on
ENV_KEY = "IDUN_KEYRING"
CONFIG_KEY = "secrets_backend"


def _config_opt_in() -> bool:
    """True if config.toml asked for the keyring backend."""
    try:
        from . import config as _cfg
        cfg = _cfg._load()
        defaults = cfg.get("defaults")
        if isinstance(defaults, dict):
            return str(defaults.get(CONFIG_KEY, "")).lower() == "keyring"
    except Exception:
        pass
    return False


def keyring_enabled() -> bool:
    """Opt-in active AND the ``keyring`` package is importable.

    Import is attempted lazily so the SDK has zero third-party dependencies
    unless the user explicitly opts in and installs ``keyring``.
    """
    if os.environ.get(ENV_KEY, "").strip() not in ("1", "true", "yes", "on"):
        if not _config_opt_in():
            return False
    try:
        import keyring  # noqa: F401  (imported to confirm availability)
        return True
    except Exception:
        return False


def _keyring():
    """Return the ``keyring`` module or ``None``."""
    if not keyring_enabled():
        return None
    try:
        import keyring
        return keyring
    except Exception:
        return None


def load_keyring(p) -> str:
    """Return the stored token for provider ``p`` or "" if none/unavailable."""
    kr = _keyring()
    if kr is None:
        return ""
    try:
        val = kr.get_password(SERVICE_NAME, p.id)
        return (val or "").strip()
    except Exception:
        return ""


def store_keyring(p, token: str) -> bool:
    """Persist ``token`` for provider ``p``. Returns True on success."""
    kr = _keyring()
    if kr is None:
        return False
    try:
        kr.set_password(SERVICE_NAME, p.id, token.strip())
        return True
    except Exception:
        return False


def delete_keyring(p) -> bool:
    """Remove any stored token for provider ``p``.

    Returns True if it was removed or was already absent — callers treat a
    missing entry as success so a delete is always safe to call.
    """
    kr = _keyring()
    if kr is None:
        return True
    try:
        kr.delete_password(SERVICE_NAME, p.id)
        return True
    except Exception:
        # keyring raises if the entry does not exist; that is still "gone"
        return True


def keyring_status(p) -> str:
    """Return \"keyring\" if a token is stored there, else \"\"."""
    return "keyring" if load_keyring(p) else ""

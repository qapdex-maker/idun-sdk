"""Credential persistence must be idempotent and correctable.

Why this file exists
--------------------
``save_credential()`` used ``os.open(..., O_CREAT | O_EXCL, 0o600)`` with no
``except FileExistsError``. The first write succeeded; every later write for the
same provider crashed with an unhandled ``FileExistsError`` and left the *old*
token in place. A user who typed a wrong key could never correct it -- the
wizard failed on every retry. That is the "stores the token wrongly, you can't
do anything" symptom reported from a real device.

The existing suite missed it for a structural reason worth remembering: every
test wrote into a fresh ``tmp_path``, so every write was a *first* write, and
``O_EXCL`` can only fail when the file already exists. The bug was unreachable
by construction. Additionally the wizard tests monkeypatched ``save_credential``
away entirely, so they asserted that the wizard *calls* the saver, never that
saving works.

Rule these tests encode: a persisting function must be tested with pre-existing
state, not only against an empty directory.
"""
from __future__ import annotations

import os
import stat

import pytest

from idun import providers


@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    """Point CONFIG_DIR at a temp dir. Never touches the real ~/.idun."""
    monkeypatch.setattr(providers, "CONFIG_DIR", str(tmp_path))
    return tmp_path


def _token_path(tmp_path, pid):
    return tmp_path / f"{pid}.token"


# --------------------------------------------------------------------------
# The core regression: overwriting must work
# --------------------------------------------------------------------------


def test_save_credential_twice_overwrites(isolated_config):
    """Saving a second time must replace the token, not crash.

    This is the exact reproduction of the reported bug: before the fix the
    second call raised FileExistsError and TOKEN_A survived.
    """
    p = providers.get_provider("openai")
    providers.save_credential(p, "TOKEN_A")
    providers.save_credential(p, "TOKEN_B")
    assert providers.resolve_credential(p) == "TOKEN_B"


def test_save_credential_repeated_corrections(isolated_config):
    """A user fixing a typo several times must end up with the last value."""
    p = providers.get_provider("groq")
    for token in ("wrong-1", "wrong-2", "wrong-3", "sk-correct"):
        providers.save_credential(p, token)
    assert providers.resolve_credential(p) == "sk-correct"


def test_save_credential_returns_path_on_overwrite(isolated_config):
    """The return value stays the token path on a repeat save."""
    p = providers.get_provider("openrouter")
    first = providers.save_credential(p, "a")
    second = providers.save_credential(p, "b")
    assert first == second == p.token_file


# --------------------------------------------------------------------------
# Security properties must survive the fix
# --------------------------------------------------------------------------


def test_overwrite_keeps_owner_only_permissions(isolated_config):
    """0600 must hold after an overwrite, not just on creation.

    A temp-file + rename implementation can silently introduce umask-derived
    permissions (0644) on the replacement file, which would leak the secret to
    other local users.
    """
    p = providers.get_provider("openai")
    providers.save_credential(p, "first")
    providers.save_credential(p, "second")
    mode = os.stat(p.token_file).st_mode
    assert oct(mode & 0o077) == "0o0", (
        f"token file is not owner-only after overwrite: {oct(mode & 0o777)}"
    )


def test_overwrite_tightens_permissive_existing_file(isolated_config, tmp_path):
    """A pre-existing world-readable token file must end up 0600.

    Covers the case where an older version (or a manual edit) left the file at
    0644: the save must not preserve those loose bits.
    """
    p = providers.get_provider("openai")
    path = _token_path(tmp_path, "openai")
    path.write_text("legacy-token", encoding="utf-8")
    os.chmod(path, 0o644)
    providers.save_credential(p, "new-token")
    mode = os.stat(p.token_file).st_mode
    assert oct(mode & 0o077) == "0o0", (
        f"permissive pre-existing file was not tightened: {oct(mode & 0o777)}"
    )
    assert providers.resolve_credential(p) == "new-token"


def test_no_leftover_temp_files(isolated_config, tmp_path):
    """An atomic implementation must not leave temp artefacts behind."""
    p = providers.get_provider("openai")
    providers.save_credential(p, "a")
    providers.save_credential(p, "b")
    names = sorted(x.name for x in tmp_path.iterdir())
    assert names == ["openai.token"], f"unexpected leftovers: {names}"


def test_token_is_stripped_on_overwrite(isolated_config):
    """Whitespace handling must stay consistent across repeat saves."""
    p = providers.get_provider("openai")
    providers.save_credential(p, "  first  ")
    providers.save_credential(p, "  second  ")
    assert providers.resolve_credential(p) == "second"


# --------------------------------------------------------------------------
# Failure handling must not destroy an existing credential
# --------------------------------------------------------------------------


def test_failed_overwrite_preserves_previous_token(isolated_config, monkeypatch):
    """If the new write fails, the previously stored token must survive.

    Losing a working credential because a replacement attempt failed would be
    worse than the original bug.
    """
    p = providers.get_provider("openai")
    providers.save_credential(p, "GOOD")

    real_replace = os.replace

    def boom(*a, **k):
        raise OSError("simulated failure")

    # Break whichever commit step the implementation uses.
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        providers.save_credential(p, "BAD")
    monkeypatch.setattr(os, "replace", real_replace)

    assert providers.resolve_credential(p) == "GOOD", (
        "a failed overwrite destroyed the existing credential"
    )


def test_directory_is_created_with_tight_permissions(monkeypatch, tmp_path):
    """A missing config dir must be created 0700, also on the overwrite path."""
    target = tmp_path / "fresh" / ".idun"
    monkeypatch.setattr(providers, "CONFIG_DIR", str(target))
    p = providers.get_provider("openai")
    providers.save_credential(p, "x")
    providers.save_credential(p, "y")
    mode = os.stat(target).st_mode
    assert stat.S_ISDIR(mode)
    assert oct(mode & 0o077) == "0o0", (
        f"config dir is not owner-only: {oct(mode & 0o777)}"
    )

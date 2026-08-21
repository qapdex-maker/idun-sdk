"""The unified `idun-wizard` must be the single source of first-run config.

Why this file exists
--------------------
Before the unification there were two wizards that wrote to TWO different files,
and neither tool read what the other wrote:

    `idun wizard`        -> ~/.idun/config.toml            (TOML, via write_config)
    `idun-multi wizard`  -> ~/.idunrc  (shell exports, append!)

`idun-multi` reads only config.toml (`config_default_provider()`); `idun` reads
only the IDUN_PROVIDER / IDUN_BACKEND env vars. So a `idun-multi wizard` run
wrote an export into .idunrc that idun-multi ignored at runtime, and a `idun
wizard` run wrote TOML that `idun` ignored. Both wizards fought over the active
provider and neither combination was consistent — exactly the "kommen wir
durcheinander" report.

The fix (Teil D): one `idun-wizard` that writes ONLY config.toml (the file both
tools actually read) for the default provider, nothing else. The two old
commands delegate to it. No .idunrc writing, anywhere.

These tests drive the wizard logic offline with a fake input stream and an
isolated config dir; they never read or write the real ~/.idun.
"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path

import pytest

from idun import providers as P


@pytest.fixture
def isolated_idun(monkeypatch):
    """Point CONFIG_DIR + the token dir at a temp location for the test."""
    d = Path(tempfile.mkdtemp(prefix="idun-wiz-"))
    monkeypatch.setattr(P, "CONFIG_DIR", str(d))
    import idun.config as C
    monkeypatch.setattr(C, "CONFIG_PATH", str(d / "config.toml"))
    C.reload()  # clear any cached config from a prior test
    yield d
    # rm -rf avoided on purpose: keep the dir; nothing under HOME was touched.


def _run_wizard(monkeypatch, inputs, isolated_idun):
    """Patch stdin with `inputs` (list of strings) and invoke the wizard."""
    from idun_cli import run_idun_wizard
    buf = io.StringIO("\n".join(inputs) + "\n")
    with contextlib.redirect_stdout(io.StringIO()):
        with monkeypatch.context() as mp:
            mp.setattr("sys.stdin", buf)
            mp.setattr("sys.stdin.isatty", lambda: True)
            rc = run_idun_wizard([])
    return rc


def test_wizard_selects_a_registry_provider(isolated_idun, monkeypatch):
    """Choosing a listed provider writes [defaults] provider = <id> to TOML."""
    import idun.config as C
    target = P.REGISTRY[0].id  # first registry id
    rc = _run_wizard(monkeypatch, ["1", "", "q"], isolated_idun)
    assert rc == 0, f"wizard returned {rc}"
    cfg = C.load_config()
    assert cfg.get("defaults", {}).get("provider") == target


def test_wizard_second_run_overwrites_cleanly(isolated_idun, monkeypatch):
    """A second run must replace the provider, not append a duplicate entry."""
    import idun.config as C
    ids = [p.id for p in P.REGISTRY]
    first, second = ids[0], ids[1]
    _run_wizard(monkeypatch, ["1", "", "q"], isolated_idun)
    _run_wizard(monkeypatch, ["2", "", "q"], isolated_idun)
    cfg = C.load_config()
    # exactly one provider recorded, and it is the second choice
    assert cfg["defaults"]["provider"] == second
    # and the raw TOML contains the id only once in [defaults]
    text = (isolated_idun / "config.toml").read_text()
    assert text.count(f'provider = "{second}"') == 1


def test_wizard_skip_keeps_provider_unset(isolated_idun, monkeypatch):
    """'s' (skip) must not set a default provider."""
    import idun.config as C
    _run_wizard(monkeypatch, ["s", "q"], isolated_idun)
    cfg = C.load_config()
    assert "provider" not in cfg.get("defaults", {}), "skip must not set a provider"


def test_wizard_does_not_write_idunrc(isolated_idun, monkeypatch):
    """The unified wizard must never touch ~/.idunrc (the old conflict source)."""
    home = isolated_idun.parent
    rc_file = home / ".idunrc"
    _run_wizard(monkeypatch, ["1", "", "q"], isolated_idun)
    assert not rc_file.exists(), "idun-wizard wrote ~/.idunrc — that is the old conflict"


def test_old_wizard_commands_delegate(isolated_idun, monkeypatch):
    """`idun wizard` and `idun-multi wizard` must route to idun-wizard.

    They must not write their own config (no .idunrc, no divergent TOML of
    their own). We assert the delegation by checking neither legacy behaviour
    survives: after a `idun-multi wizard` style invocation the only thing on
    disk is the unified config.toml default.
    """
    import idun.config as C
    from idun_cli import cmd_wizard as idun_wizard_cmd
    from idun_multi import cmd_wizard as multi_wizard_cmd

    buf = io.StringIO("1\n\nq\n")
    with contextlib.redirect_stdout(io.StringIO()):
        with monkeypatch.context() as mp:
            mp.setattr("sys.stdin", buf)
            mp.setattr("sys.stdin.isatty", lambda: True)
            # both old commands should now behave like the unified wizard
            assert idun_wizard_cmd([]) in (0, None)
            assert multi_wizard_cmd(object()) in (0, None)
    # no .idunrc from either path
    assert not (isolated_idun.parent / ".idunrc").exists()
    # and TOML reflects a single chosen default provider
    assert "provider" in C.load_config().get("defaults", {})

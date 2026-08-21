"""The two wizards must be SEPARATE and each actually work (teil D, corrected).

Context / correction
--------------------
An earlier "unification" collapsed both wizards into one `run_idun_wizard`
that only offered LLM providers and, worse, never printed the provider table
(the table build was dead code: `print(...) if False else None`). So both
`idun wizard` and `idun-multi wizard` showed only "#) id / s) skip / q) quit"
with nothing to select.

The user's actual requirement (stated after the wrong unification):
- `idun wizard`   -> Azure AI Foundry client setup (endpoint / project / agent).
- `idun-multi wizard` -> multi-provider LLM setup (the 17 registry providers).

They must NOT be merged into one. Each writes ONLY to ~/.idun/config.toml
(no .idunrc) so there is no cross-file conflict, but they manage different
sections. These tests run the wizards with a faked TTY + temp config dir and
assert the real, usable behaviour.
"""
from __future__ import annotations

import io
import contextlib
from unittest import mock

import pytest

from idun import providers as P


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    d = tmp_path / "idun"
    d.mkdir()
    monkeypatch.setattr(P, "CONFIG_DIR", str(d))
    import idun.config as C
    monkeypatch.setattr(C, "CONFIG_PATH", str(d / "config.toml"))
    C.reload()
    return d


def _run(args, inp: str, fn):
    """Run wizard fn with faked TTY stdin, return (rc, stdout)."""
    buf = io.StringIO(inp)
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        with mock.patch("sys.stdin", buf), \
             mock.patch("sys.stdin.isatty", return_value=True), \
             mock.patch("getpass.getpass", return_value=""):
            rc = fn(args)
    return rc, out.getvalue()


def test_idun_wizard_is_azure_setup(isolated):
    """`idun wizard` drives Azure config (base/project/agent), not providers."""
    from idun_cli import cmd_wizard
    rc, out = _run([], "https://x.services.ai.azure.com\nmyproj\nmyagent\nq\n", cmd_wizard)
    assert rc == 0
    assert "azure" in out.lower() or "foundry" in out.lower()
    # It should have written an azure section to config.toml
    txt = (isolated / "config.toml").read_text(encoding="utf-8")
    assert "azure" in txt.lower()
    assert "base" in txt.lower()


def test_idun_multi_wizard_lists_providers_and_selects(isolated):
    """`idun-multi wizard` shows the provider table and can select one."""
    from idun_multi import cmd_wizard as mw
    # choose provider #1 (first registry provider), then quit
    rc, out = _run([], "1\nq\n", mw)
    assert rc == 0
    # The provider table must actually be printed (the old bug hid it)
    assert "openai" in out or "openrouter" in out or "anthropic" in out, (
        "provider table was not printed; wizard is unusable"
    )
    txt = (isolated / "config.toml").read_text(encoding="utf-8")
    assert "provider" in txt.lower()


def test_idun_multi_wizard_skip_keeps_provider_unset(isolated):
    rc, out = _run([], "s\nq\n", __import__("idun_multi").cmd_wizard)
    assert rc == 0
    # skip must NOT write a provider default
    if (isolated / "config.toml").exists():
        txt = (isolated / "config.toml").read_text(encoding="utf-8")
        assert "provider =" not in txt


def test_idun_wizard_skip_is_safe(isolated):
    """Aborting the Azure wizard leaves config untouched / no crash."""
    from idun_cli import cmd_wizard
    rc, out = _run([], "q\n", cmd_wizard)
    assert rc == 0
    # config may or may not exist, but must not contain a provider default
    if (isolated / "config.toml").exists():
        txt = (isolated / "config.toml").read_text(encoding="utf-8")
        assert "provider" not in txt.lower()


def test_no_shared_unified_wizard_symbol():
    """The collapsed `run_idun_wizard` must be gone; both wizards are separate."""
    import idun_cli
    import idun_multi
    assert not hasattr(idun_cli, "run_idun_wizard"), (
        "run_idun_wizard should be removed — wizards are separate again"
    )
    assert idun_cli.cmd_wizard is not idun_multi.cmd_wizard, (
        "idun wizard and idun-multi wizard must not share an implementation"
    )

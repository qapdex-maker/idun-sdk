"""Offline tests for the `idun wizard` command (no network, no real TTY).

Covers the wizard rework:
  - TTY safety: a piped (non-interactive) invocation must exit 1, never hang.
  - Quit (q / empty) aborts with no config written and returns 0.
  - Skip (s) keeps registry defaults and still writes a config (no provider).
  - Generic "other" endpoint records a base URL.
  - A normal choice records the selected provider.
"""
import io
import sys

import idun_cli as cli


def _run_wizard(monkeypatch, answers, stdin_is_tty=True):
    """Drive cmd_wizard with a queue of canned answers on a fake stdin.

    answers: list of strings (one per prompt). We serve them via a StringIO
    and also monkeypatch sys.stdin.isatty. Both stdout and stderr are captured
    because the UI helpers print to stderr.
    """
    # fake an interactive TTY by default
    monkeypatch.setattr(sys, "stdin", io.StringIO("\n".join(answers) + "\n"))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: stdin_is_tty)

    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    # avoid any real network / credential writes to the user's home
    monkeypatch.setattr(cli, "_save_backend_token", lambda b, t: "/tmp/fake.token")
    monkeypatch.setattr(cli, "_wizard_test_call", lambda b: None)

    rc = cli.cmd_wizard(object())
    return rc, out.getvalue() + err.getvalue()


def test_wizard_refuses_non_tty(monkeypatch):
    """Piped / non-interactive invocation must never hang or crash."""
    rc, out = _run_wizard(monkeypatch, [], stdin_is_tty=False)
    assert rc == 1, "must refuse to run without a TTY"
    assert "TTY" in out or "interactive" in out


def test_wizard_quit_makes_no_changes(monkeypatch, tmp_path):
    """'q' at the first prompt aborts cleanly with rc 0 and no config file."""
    cfg_path = tmp_path / "config.toml"

    def fake_write(cfg):
        cfg_path.write_text("# test\n", encoding="utf-8")
        return str(cfg_path)

    monkeypatch.setattr("idun.config.write_config", fake_write)
    rc, out = _run_wizard(monkeypatch, ["q"])
    assert rc == 0, "quit should be a clean exit"
    assert "no changes" in out.lower() or "abort" in out.lower()
    assert not cfg_path.exists(), "quit must not write a config"


def test_wizard_skip_keeps_defaults(monkeypatch, tmp_path):
    """'s' skips backend setup; config written with no provider key."""
    written = {}

    def fake_write(cfg):
        written.update(cfg)
        p = tmp_path / "config.toml"
        p.write_text("# test\n", encoding="utf-8")
        return str(p)

    monkeypatch.setattr("idun.config.write_config", fake_write)
    rc, out = _run_wizard(monkeypatch, ["s", ""])  # skip, then blank theme
    assert rc == 0
    assert "defaults" in written, "config must contain a [defaults] section"
    assert "provider" not in written.get("defaults", {}), \
        "skip must not set a provider"


def test_wizard_other_records_base(monkeypatch, tmp_path):
    """Option 5 'other' (generic OpenAI-compatible) records the base URL."""
    written = {}

    def fake_write(cfg):
        written.update(cfg)
        p = tmp_path / "config.toml"
        p.write_text("# test\n", encoding="utf-8")
        return str(p)

    monkeypatch.setattr("idun.config.write_config", fake_write)
    rc, out = _run_wizard(
        monkeypatch,
        ["5", "https://example.invalid/v1", "sk-fake", "my-model", ""],
    )
    assert rc == 0
    assert written.get("openai", {}).get("base") == "https://example.invalid/v1", \
        "generic endpoint base URL must be saved"
    assert written.get("openai", {}).get("model") == "my-model"


def test_wizard_azure_selects_provider(monkeypatch, tmp_path):
    """Option 1 'azure' records the provider + base."""
    written = {}

    def fake_write(cfg):
        written.update(cfg)
        p = tmp_path / "config.toml"
        p.write_text("# test\n", encoding="utf-8")
        return str(p)

    monkeypatch.setattr("idun.config.write_config", fake_write)
    rc, out = _run_wizard(
        monkeypatch,
        ["1", "https://res.services.ai.azure.com", "proj", "tid", ""],
    )
    assert rc == 0
    assert written["defaults"]["provider"] == "azure"
    assert written["defaults"]["base"] == "https://res.services.ai.azure.com"

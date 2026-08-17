"""Tests for the v0.4 config.toml support (offline, hermetic)."""
import textwrap

import pytest

import idun.config as cfg
from idun import providers as P


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Point the config module at a temp file and clear its cache."""
    path = tmp_path / "config.toml"
    monkeypatch.setattr(cfg, "CONFIG_PATH", str(path))
    cfg.reload()
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    yield
    cfg.reload()


def _write(text: str):
    # write through the same path the module reads
    with open(cfg.CONFIG_PATH, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(text))


def test_empty_config_returns_no_overrides():
    _write("")
    p = P.get_provider("groq")
    assert cfg.config_provider_model("groq") == ""
    assert cfg.config_provider_base("groq") == ""
    assert cfg.config_provider_key("groq") == ""
    # registry defaults still apply
    assert p.resolved_model() == p.default_model
    assert p.resolved_base() == p.base


def test_section_model_and_base_override():
    _write("""
    [defaults]
    provider = "groq"

    [groq]
    model = "mixtral-8x7b-32768"
    base = "https://proxy.example.com/openai/v1"

    [openai]
    model = "gpt-4o-mini"
    """)
    groq = P.get_provider("groq")
    assert cfg.config_provider_model("groq") == "mixtral-8x7b-32768"
    assert cfg.config_provider_base("groq") == "https://proxy.example.com/openai/v1"
    assert cfg.config_default_provider() == "groq"
    # resolved_* honours config only when no env is set
    assert groq.resolved_model() == "mixtral-8x7b-32768"
    assert groq.resolved_base() == "https://proxy.example.com/openai/v1"


def test_env_wins_over_config(monkeypatch):
    _write("""
    [groq]
    model = "mixtral-8x7b-32768"
    """)
    monkeypatch.setenv("IDUN_GROQ_MODEL", "llama-3.1-8b-instant")
    groq = P.get_provider("groq")
    assert groq.resolved_model() == "llama-3.1-8b-instant"


def test_config_api_key_used_as_last_resort():
    _write("""
    [groq]
    api_key = "cfg-secret-key"
    """)
    groq = P.get_provider("groq")
    # no env, no token file -> config key is resolved
    assert P.resolve_credential(groq) == "cfg-secret-key"


def test_token_file_beats_config_key(monkeypatch, tmp_path):
    _write("""
    [groq]
    api_key = "cfg-secret-key"
    """)
    token_file = tmp_path / "groq.token"
    token_file.write_text("file-secret-key", encoding="utf-8")
    # provider.token_file is derived from providers.CONFIG_DIR; point P's there
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    # re-fetch provider so token_file path uses the patched CONFIG_DIR
    groq = P.get_provider("groq")
    assert P.resolve_credential(groq) == "file-secret-key"


def test_boolean_scalar_parsing():
    # ensure the minimal TOML parser handles booleans without crashing
    _write("""
    [defaults]
    provider = "groq"
    theme = "c64"
    """)
    assert cfg.config_default_provider() == "groq"
    assert cfg.config_theme() == "c64"


def test_reload_clears_cache():
    _write("[groq]\nmodel = \"a\"\n")
    assert cfg.config_provider_model("groq") == "a"
    _write("[groq]\nmodel = \"b\"\n")
    cfg.reload()
    assert cfg.config_provider_model("groq") == "b"

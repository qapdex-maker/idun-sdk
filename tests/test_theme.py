"""Tests for the v0.5 theme system."""
import importlib

import idun.retro as R


def test_default_theme_is_classic():
    assert R.theme() in R.list_themes()


def test_set_theme_switches_role_and_roundtrip():
    orig = R.theme()
    try:
        active = R.set_theme("gameboy")
        assert active == "gameboy"
        assert R.theme() == "gameboy"
        # gameboy frame role maps to a real colour code
        assert R._CODES.get(R.ROLE["frame"]) is not None
    finally:
        R.set_theme(orig)


def test_unknown_theme_falls_back_to_classic():
    orig = R.theme()
    try:
        active = R.set_theme("does-not-exist")
        assert active == "classic"
        assert R.theme() == "classic"
    finally:
        R.set_theme(orig)


def test_all_themes_resolve_to_valid_codes():
    for tid in R.list_themes():
        for role, color in R.THEMES[tid].items():
            assert color in R._CODES, f"{tid}.{role} -> {color} invalid"


def test_env_theme_applied_at_import(monkeypatch):
    monkeypatch.setenv("IDUN_THEME", "c64")
    # re-import to trigger _apply_env_theme with the env var set
    import sys
    sys.modules.pop("idun.retro", None)
    R2 = importlib.import_module("idun.retro")
    try:
        assert R2.theme() == "c64"
    finally:
        monkeypatch.delenv("IDUN_THEME", raising=False)
        sys.modules.pop("idun.retro", None)
        importlib.import_module("idun.retro")

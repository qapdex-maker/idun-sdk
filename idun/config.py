"""Configuration file support for the Idun SDK (v0.4).

A single TOML file at ``~/.idun/config.toml`` is the primary configuration
source. Environment variables always win (so CI / one-off overrides keep
working), and the provider registry defaults are the final fallback.

The parser is deliberately minimal and stdlib-only: it understands the small
subset of TOML the SDK needs (``[section]`` headers, ``key = "value"`` /
``key = 123`` / ``key = true`` scalars) so the package keeps working on
Python 3.8+ with no ``tomllib`` dependency. On Python 3.11+ the real
``tomllib`` is used when available.

Example ``~/.idun/config.toml``::

    [defaults]
    provider = "groq"
    theme = "c64"

    [groq]
    model = "llama-3.3-70b-versatile"

    [openai]
    base = "https://my-proxy.example.com/v1"
    model = "gpt-4o-mini"

    [anthropic]
    api_key = "sk-..."   # optional; the ~/.idun/<id>.token file is preferred

Security note: storing an API key in plaintext TOML is convenient but the
``~/.idun/<id>.token`` file (mode 0600, owner-only) is the more secure home for
secrets. ``config.toml`` is read with the same 0700 directory expectation, but
keys placed here are in the same file as harmless settings, so prefer the
token file for anything sensitive.
"""
from __future__ import annotations

import os

from .providers import CONFIG_DIR

CONFIG_PATH = os.path.join(CONFIG_DIR, "config.toml")

# Cached parsed config so repeated lookups do not re-read the file every call.
_cache: dict | None = None


def _toml_scalar(val: str):
    """Coerce a TOML scalar literal into a Python value (subset)."""
    s = val.strip()
    if not s:
        return ""
    if s[0] in ('"', "'"):
        # strip matching quotes, unescape the basic escapes we care about
        quote = s[0]
        body = s[1:]
        if body.endswith(quote):
            body = body[:-1]
        if quote == '"':
            body = body.replace('\\"', '"').replace("\\\\", "\\")
        return body
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _parse_toml(text: str) -> dict:
    """Parse the TOML subset the SDK needs into nested dicts."""
    root: dict = {}
    cur = root
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            # [section] or [a.b.c] — we only use a single level of section
            end = line.find("]")
            if end == -1:
                continue
            name = line[1:end].strip()
            cur = root.setdefault(name, {})
        elif "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            if not key:
                continue
            cur[key] = _toml_scalar(val)
    return root


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        _cache = {}
        return _cache
    try:
        import tomllib  # Python 3.11+
        _cache = tomllib.loads(text)
    except ModuleNotFoundError:
        _cache = _parse_toml(text)
    except Exception:
        # corrupt config must never crash the SDK — fall back to no config
        _cache = {}
    return _cache


def reload() -> None:
    """Force a re-read of the config file on the next lookup (test hook)."""
    global _cache
    _cache = None


def config_provider_model(pid: str) -> str:
    """Model override from ``[<pid>] model = ...`` (empty string if unset)."""
    cfg = _load()
    section = cfg.get(pid)
    if isinstance(section, dict):
        m = section.get("model")
        if isinstance(m, str):
            return m
    return ""


def config_provider_base(pid: str) -> str:
    """Base-url override from ``[<pid>] base = ...`` (empty if unset)."""
    cfg = _load()
    section = cfg.get(pid)
    if isinstance(section, dict):
        b = section.get("base")
        if isinstance(b, str):
            return b
    return ""


def config_provider_key(pid: str) -> str:
    """API key from ``[<pid>] api_key = ...`` (empty if unset)."""
    cfg = _load()
    section = cfg.get(pid)
    if isinstance(section, dict):
        k = section.get("api_key")
        if isinstance(k, str):
            return k.strip()
    return ""


def config_default_provider() -> str:
    """Default provider from ``[defaults] provider = ...`` (empty if unset)."""
    cfg = _load()
    d = cfg.get("defaults")
    if isinstance(d, dict):
        p = d.get("provider")
        if isinstance(p, str):
            return p.strip().lower()
    return ""


def config_theme() -> str:
    """Theme name from ``[defaults] theme = ...`` (empty if unset)."""
    cfg = _load()
    d = cfg.get("defaults")
    if isinstance(d, dict):
        t = d.get("theme")
        if isinstance(t, str):
            return t.strip().lower()
    return ""


__all__ = [
    "CONFIG_PATH", "load_config", "reload",
    "config_provider_model", "config_provider_base",
    "config_provider_key", "config_default_provider", "config_theme",
]


def load_config() -> dict:
    """Return the parsed config dict (read-through cache)."""
    return _load()

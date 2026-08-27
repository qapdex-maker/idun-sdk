"""Cheap on-disk cache for review chunk results.

Re-running ``idun-multi review`` over the same PR is expensive (it calls
several LLM providers per diff chunk). This module stores the structured
findings per ``(repo, pr, chunk_index, chunk_hash)`` so a repeat run can skip
the LLM calls unless ``--no-cache`` is passed.

Only findings (provider id + parsed text) are stored — never the raw diff and
never any secret. Path lives under the idun config dir (``~/.idun``).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

CACHE_FILE = os.path.join(os.path.expanduser("~"), ".idun", ".review_cache.json")

# Bump when the on-disk schema changes.
_SCHEMA = 1


def _chunk_key(repo: str, pr: str, index: int, chunk: str) -> str:
    h = hashlib.sha256(chunk.encode("utf-8", "replace")).hexdigest()[:16]
    return f"{repo}#{pr}#{index}#{h}"


def _load() -> dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("schema") != _SCHEMA:
            return {"schema": _SCHEMA, "entries": {}}
        return data
    except (OSError, ValueError):
        return {"schema": _SCHEMA, "entries": {}}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, CACHE_FILE)
    try:
        os.chmod(CACHE_FILE, 0o600)
    except OSError:
        pass


def get(repo: str, pr: str, index: int, chunk: str) -> Optional[str]:
    """Return the cached raw provider review text for a chunk, or None."""
    data = _load()
    key = _chunk_key(repo, pr, index, chunk)
    entry = data["entries"].get(key)
    if not entry:
        return None
    return entry.get("text")


def put(repo: str, pr: str, index: int, chunk: str, text: str) -> None:
    """Store the raw provider review text for a chunk."""
    data = _load()
    key = _chunk_key(repo, pr, index, chunk)
    data["entries"][key] = {"text": text}
    _save(data)


def clear() -> None:
    """Drop the whole cache file."""
    try:
        os.remove(CACHE_FILE)
    except OSError:
        pass

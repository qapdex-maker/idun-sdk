"""Contoso / curated prompt packs for the Idun CLI.

Packs live in idun/data/prompt_packs/*.json and are resolvable after
`pip install` (no extra asset path needed). Offline, stdlib-only.
"""
import json
import os

PACKS_DIR = os.path.join(os.path.dirname(__file__), "data", "prompt_packs")


def list_packs() -> list:
    """Return metadata for every available pack (name, title, description, count)."""
    packs = []
    if not os.path.isdir(PACKS_DIR):
        return packs
    for fn in sorted(os.listdir(PACKS_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(PACKS_DIR, fn), encoding="utf-8") as f:
                data = json.load(f)
            packs.append({
                "name": data.get("name", fn[:-5]),
                "title": data.get("title", fn),
                "description": data.get("description", ""),
                "count": len(data.get("prompts", [])),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return packs


def load_pack(name: str) -> dict:
    """Load a pack by name (filename stem or `name` field). Raises FileNotFoundError."""
    for fn in os.listdir(PACKS_DIR):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(PACKS_DIR, fn)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("name") == name or fn[:-5] == name:
            return data
    raise FileNotFoundError(f"No prompt pack named {name!r} in {PACKS_DIR}")


def get_prompt(name: str, key: str) -> str:
    """Return the prompt text for `key` inside pack `name`. Raises KeyError/FileNotFoundError."""
    pack = load_pack(name)
    for p in pack.get("prompts", []):
        if p.get("key") == key:
            return p["prompt"]
    available = ", ".join(p.get("key", "?") for p in pack.get("prompts", []))
    raise KeyError(f"Prompt key {key!r} not in pack {name!r}. Available: {available}")


def run_pack(name: str, keys=None, client=None, max_output_tokens: int = 4096):
    """Run one or many prompts from a pack and return (key, result) pairs.

    keys=None (default) runs EVERY prompt in the pack (batch). Pass a list to
    run a subset. Returns a list of (key, result) where result is either an
    IdunResult (success) or an Exception (that prompt failed — the rest of the
    batch still completes). Network/offline: the client call is the only live
    part; pack loading + key resolution are offline.
    """
    from .client import IdunClient
    pack = load_pack(name)
    prompts = pack.get("prompts", [])
    if keys is None:
        selected = [(p["key"], p["prompt"]) for p in prompts]
    else:
        by_key = {p["key"]: p["prompt"] for p in prompts}
        selected = [(k, by_key[k]) for k in keys]
    if client is None:
        client = IdunClient()
    out = []
    for k, prompt in selected:
        try:
            out.append((k, client.complete(prompt, max_output_tokens)))
        except Exception as e:  # one bad prompt must not kill the whole batch
            out.append((k, e))
    return out


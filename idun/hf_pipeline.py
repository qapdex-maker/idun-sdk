"""Hugging Face pipeline integration for the Idun SDK (stdlib-only).

Two layers, both usable without `transformers`/PyTorch installed:

1. **Inference** — call any serverless HF model via the Inference API
   (`api-inference.huggingface.co`). Same as ``backends.complete_hf`` but
   with richer error mapping and support for conversational + pipeline tasks.

2. **Hub** — inspect and publish to the HF Hub directly from the CLI:
   ``whoami`` (token validity + user), ``model_status`` (exists? gated?
   private?), and ``upload`` (create a repo + push files). This is the
   "HF pipeline" glue: an Idun agent can produce artefacts and publish them
   to a Hub repo without leaving the terminal.

Stdlib-only (urllib) so it runs headless on Termux/Android.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

HF_API = "https://huggingface.co"
# Inference now goes through the OpenAI-compatible router. The old
# api-inference.huggingface.co host was retired and no longer resolves
# (same dead host as the old `hf` provider, BUG 5/BUG 7). The router exposes
# /v1/chat/completions, so hf_infer speaks the OpenAI dialect.
HF_INFERENCE = "https://router.huggingface.co/v1"

# Common serverless models for quick trials. Not exhaustive. Must exist on the
# router — verified against the live model list during the BUG 7 fix.
SUGGESTED_TEXT_MODELS = (
    "deepseek-ai/DeepSeek-V4-Flash",
    "google/gemma-4-26B-A4B-it",
    "Qwen/Qwen3.5-9B",
)


# --------------------------------------------------------------------------
# Token handling (shared with backends.py)
# --------------------------------------------------------------------------

def load_hf_token() -> str:
    """HF token from env or the idun token store.

    Order: HF_TOKEN / HUGGING_FACE_HUB_TOKEN env, then ~/.idun/hf.token (the
    file written by `idun-multi login --backend hf` and the unified wizard).
    Kept stdlib-only; falls back to the legacy ~/hf_token.txt if present.
    """
    env = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if env:
        return env
    idun_file = os.path.join(os.path.expanduser("~"), ".idun", "hf.token")
    try:
        with open(idun_file, encoding="utf-8") as f:
            tok = f.read().strip()
            if tok:
                return tok
    except OSError:
        pass
    try:
        with open(os.path.join(os.path.expanduser("~"), "hf_token.txt"),
                  encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------

def _extract_text(raw: object) -> str:
    """Pull assistant text out of an OpenAI-style response."""
    if isinstance(raw, dict):
        try:
            return raw["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return json.dumps(raw, ensure_ascii=False)[:400]
    return str(raw or "")


def hf_infer(prompt: str, token: str = "", model: str = "deepseek-ai/DeepSeek-V4-Flash",
             timeout: int = 120, max_new_tokens: int = 1024) -> str:
    """Run a prompt through the HF Inference router (OpenAI-compatible /v1).

    Returns the generated text. Raises RuntimeError on HTTP error with the
    response body so callers can surface model-specific issues (e.g. a model
    still loading, or gated-access denied).
    """
    url = f"{HF_INFERENCE}/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_new_tokens,
    }
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"HF inference HTTP {e.code}: {msg}") from e
    return _extract_text(data)


# --------------------------------------------------------------------------
# Hub
# --------------------------------------------------------------------------

def hf_whoami(token: str) -> dict:
    """Return the HF Hub user profile for `token` (GET /api/whoami-v2).

    Raises RuntimeError on auth failure (401) or network error.
    """
    if not token:
        raise RuntimeError("hf_whoami needs an HF token (HF_TOKEN / ~/hf_token.txt).")
    req = urllib.request.Request(
        f"{HF_API}/api/whoami-v2",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HF whoami HTTP {e.code}: {msg}") from e


def hf_model_status(model: str, token: str = "") -> dict:
    """Probe a model repo on the Hub.

    Returns a dict with keys: exists (bool), gated (str|None), private (bool),
    pipeline_tag (str|None), and an `error` key if the request failed.
    A 404 sets exists=False rather than raising.
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(
        f"{HF_API}/api/models/{model}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return {
            "exists": True,
            "gated": data.get("gated"),
            "private": bool(data.get("private")),
            "pipeline_tag": data.get("pipeline_tag"),
            "error": None,
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"exists": False, "gated": None, "private": False,
                    "pipeline_tag": None, "error": None}
        msg = e.read().decode("utf-8", "replace")[:300]
        return {"exists": False, "gated": None, "private": False,
                "pipeline_tag": None, "error": f"HTTP {e.code}: {msg}"}


def hf_upload(model: str, files: dict, token: str,
              private: bool = False) -> dict:
    """Push `files` ({path: content}) to a Hub repo.

    Uses the official `huggingface_hub` client when available (handles the
    create-repo + commit flow correctly against the current Hub API). If the
    package is not installed, raises a clear RuntimeError telling the user to
    `pip install huggingface_hub` (kept optional so the SDK stays stdlib-only
    for inference/whoami/status).

    Returns the commit info dict on success.
    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise RuntimeError(
            "hf push needs the 'huggingface_hub' package. "
            "Install it with: pip install huggingface_hub  (or use the "
            "'huggingface-cli upload' command directly).")
    api = HfApi(token=token)
    repo_url = api.create_repo(model, private=private, exist_ok=True)
    ops = []
    from huggingface_hub import CommitOperationAdd
    import tempfile
    import os as _os
    for path, content in files.items():
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=f"_{_os.path.basename(path)}", delete=False,
            encoding="utf-8")
        tmp.write(content)
        tmp.close()
        ops.append(CommitOperationAdd(path_in_repo=path, path_or_fileobj=tmp.name))
    commit = api.create_commit(model, operations=ops,
                               commit_message="idun-sdk hf push")
    return {"repo_url": str(repo_url), "commit": str(commit)}


__all__ = [
    "load_hf_token", "hf_infer", "hf_whoami", "hf_model_status", "hf_upload",
    "SUGGESTED_TEXT_MODELS",
]

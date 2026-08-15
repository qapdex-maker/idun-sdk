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
HF_INFERENCE = "https://api-inference.huggingface.co"

# Common serverless models for quick trials. Not exhaustive.
SUGGESTED_TEXT_MODELS = (
    "microsoft/phi-3-mini-4k-instruct",
    "google/gemma-2-2b-it",
    "meta-llama/Llama-3.1-8B-Instruct",
)


# --------------------------------------------------------------------------
# Token handling (shared with backends.py)
# --------------------------------------------------------------------------

def load_hf_token() -> str:
    """HF token from HF_TOKEN / HUGGING_FACE_HUB_TOKEN env or ~/hf_token.txt."""
    env = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if env:
        return env
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
    """Pull generated text out of the various HF Inference response shapes."""
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, dict):
        gt = raw.get("generated_text")
        if isinstance(gt, dict):
            return gt.get("content") or gt.get("text") or ""
        return str(gt or "")
    return str(raw or "")


def hf_infer(prompt: str, token: str = "", model: str = "microsoft/phi-3-mini-4k-instruct",
             timeout: int = 120, max_new_tokens: int = 1024) -> str:
    """Run a prompt through the HF Inference API (serverless).

    Returns the generated text. Raises RuntimeError on HTTP error with the
    response body so callers can surface model-specific issues (e.g. a model
    still loading, or gated-access denied).
    """
    url = f"{HF_INFERENCE}/models/{model}"
    body = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_new_tokens, "return_full_text": False},
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
    import tempfile, os as _os
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

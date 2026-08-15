"""Multi-backend completion for the Idun SDK.

Adds non-Azure backends behind the SAME IdunClient API so the rest of the
code (CLI, MCP, Conversation) never changes:

  IDUN_BACKEND=azure     -> Azure AI Foundry (default, unchanged behaviour)
  IDUN_BACKEND=hf        -> Hugging Face Inference API (Bearer HF_TOKEN)
  IDUN_BACKEND=github    -> GitHub Models (Bearer GITHUB_TOKEN, free tier)
  IDUN_BACKEND=ollama    -> local Ollama server (no auth, no cost)

Every backend returns a plain (text, model_name) tuple which the client
wraps into an IdunResult (with an empty step list, since these backends do
not expose Idun's web_search tool-agent trajectory).

Stdlib-only (urllib) so it runs headless on Termux/Android.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# --------------------------------------------------------------------------
# Hugging Face
# --------------------------------------------------------------------------

HF_TOKEN_FILE = os.path.join(os.path.expanduser("~"), "hf_token.txt")
HF_DEFAULT_MODEL = "microsoft/phi-3-mini-4k-instruct"


def load_hf_token() -> str:
    """Return HF token from HF_TOKEN env or ~/hf_token.txt, else ''.

    The token is never echoed. A missing token still allows anonymous
    (rate-limited) access to the HF Inference API.
    """
    env = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if env:
        return env
    try:
        return open(HF_TOKEN_FILE, "r", encoding="utf-8").read().strip()
    except OSError:
        return ""


def save_hf_token(token: str) -> None:
    """Persist an HF token to ~/hf_token.txt (0600)."""
    os.makedirs(os.path.dirname(HF_TOKEN_FILE), exist_ok=True)
    with open(HF_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token.strip())
    try:
        os.chmod(HF_TOKEN_FILE, 0o600)
    except OSError:
        pass


def _hf_extract_text(raw: object) -> str:
    """Pull generated text out of the various HF Inference shapes."""
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, dict):
        # conversational task returns {"generated_text": {"role","content"}}
        gt = raw.get("generated_text")
        if isinstance(gt, dict):
            return gt.get("content") or gt.get("text") or ""
        return str(gt or "")
    return str(raw or "")


def complete_hf(prompt: str, token: str, model: str, timeout: int = 120,
                max_new_tokens: int = 1024) -> tuple[str, str]:
    """Run a prompt through the HF Inference API (serverless).

    Returns (text, model). Raises RuntimeError on HTTP error with the body.
    """
    url = f"https://api-inference.huggingface.co/models/{model}"
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
        raise RuntimeError(f"HF HTTP {e.code}: {msg}") from e
    return _hf_extract_text(data), model


# --------------------------------------------------------------------------
# GitHub Models (free tier, OpenAI-compatible)
#
# NOTE: GitHub Models inference is bound to Copilot / VS Code and is NOT
# freely callable with a plain PAT at models.inference.ai.azure.com — that
# endpoint returns 404 for standard PATs. The code below is kept for
# environments where the endpoint is reachable (e.g. GitHub Codespaces /
# Copilot routing). For a guaranteed-free path use the `hf` backend instead.
# --------------------------------------------------------------------------

GITHUB_TOKEN_FILE = os.path.join(os.path.expanduser("~"), "github_token.txt")
GITHUB_DEFAULT_MODEL = "gpt-4o-mini"


def load_github_token() -> str:
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env
    try:
        return open(GITHUB_TOKEN_FILE, "r", encoding="utf-8").read().strip()
    except OSError:
        return ""


def save_github_token(token: str) -> None:
    os.makedirs(os.path.dirname(GITHUB_TOKEN_FILE), exist_ok=True)
    with open(GITHUB_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token.strip())
    try:
        os.chmod(GITHUB_TOKEN_FILE, 0o600)
    except OSError:
        pass


def complete_github(prompt: str, token: str, model: str, timeout: int = 120,
                    max_tokens: int = 1024) -> tuple[str, str]:
    """Run a prompt through GitHub Models (OpenAI-compatible chat endpoint).

    Returns (text, model). Requires a GitHub PAT (fine-grained or classic)
    with no special scopes for the inference endpoint.
    """
    url = "https://models.inference.ai.azure.com/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"GitHub HTTP {e.code}: {msg}") from e
    # OpenAI-shaped: choices[0].message.content
    text = ""
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        text = json.dumps(data, ensure_ascii=False)[:400]
    return text, model


# --------------------------------------------------------------------------
# Ollama (local, free)
# --------------------------------------------------------------------------

OLLAMA_DEFAULT_BASE = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "llama3.1"


def complete_ollama(prompt: str, base: str, model: str, timeout: int = 300) -> tuple[str, str]:
    """Run a prompt through a local Ollama /api/generate endpoint."""
    url = f"{base.rstrip('/')}/api/generate"
    body = {"model": model, "prompt": prompt, "stream": False}
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"Ollama HTTP {e.code}: {msg}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama unreachable at {base}: {e.reason}") from e
    return data.get("response", ""), model


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

VALID_BACKENDS = ("azure", "hf", "github", "ollama")


def backend_from_env() -> str:
    return os.environ.get("IDUN_BACKEND", "azure").strip().lower()


def _extract_last_user(messages: list) -> str:
    """Pull the last user turn out of a Foundry message-list (for non-Idun backends)."""
    if isinstance(messages, str):
        return messages
    for m in reversed(messages):
        if m.get("role") == "user":
            for c in m.get("content", []):
                if c.get("type") == "input_text":
                    return c.get("text", "")
            # plain string content fallback
            if isinstance(m.get("content"), str):
                return m["content"]
    # fallback: first available text
    return str(messages)


def run_external(backend: str, prompt: str, *, hf_token: str = "",
                 hf_model: str = HF_DEFAULT_MODEL, github_token: str = "",
                 github_model: str = GITHUB_DEFAULT_MODEL, ollama_base: str = OLLAMA_DEFAULT_BASE,
                 ollama_model: str = OLLAMA_DEFAULT_MODEL, timeout: int = 300,
                 max_tokens: int = 1024) -> tuple[str, str]:
    """Dispatch a single prompt to the chosen non-azure backend.

    Returns (text, model_name). Raises ValueError on unknown backend.
    """
    if backend == "hf":
        return complete_hf(prompt, hf_token, hf_model, timeout=timeout,
                           max_new_tokens=max_tokens)
    if backend == "github":
        if not github_token:
            raise RuntimeError("GitHub backend needs GITHUB_TOKEN (env or ~/github_token.txt).")
        return complete_github(prompt, github_token, github_model,
                               timeout=timeout, max_tokens=max_tokens)
    if backend == "ollama":
        return complete_ollama(prompt, ollama_base, ollama_model, timeout=timeout)
    raise ValueError(f"unknown backend: {backend!r}")

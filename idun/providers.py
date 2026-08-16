"""Provider registry for the Idun SDK — the multi-provider core.

Replaces the hand-wired per-backend functions in ``backends.py`` with a single
declarative registry. Every provider is described by a :class:`Provider`
record; almost all modern inference APIs speak the OpenAI
``/v1/chat/completions`` dialect, so one transport covers them all and only
the odd ones out (Azure Foundry responses API, HF Inference) need a custom
call function.

Design rules:
  * stdlib only (urllib) so it runs headless on Termux/Android
  * credentials come from env first, then ~/.idun/<id>.token, never echoed
  * adding a provider = adding one Provider(...) entry, no other edits

Public API:
    list_providers()            -> tuple[Provider, ...]
    get_provider(pid)           -> Provider
    resolve_credential(p)       -> str
    save_credential(p, token)   -> None
    complete(pid, prompt, ...)  -> Completion
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from typing import Callable  # noqa: F401  (re-exported by the public API)

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".idun")

# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Completion:
    """Result of a single provider round-trip."""

    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class Provider:
    """Declarative description of one inference provider."""

    id: str
    label: str
    base: str
    default_model: str
    env_keys: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    free_tier: bool = False
    needs_key: bool = True
    notes: str = ""
    # transport: "openai" (chat/completions) / "anthropic" / "hf". Custom
    # transports register in _TRANSPORTS instead of via this field.
    transport: str = "openai"

    # ---- credential storage -------------------------------------------
    @property
    def token_file(self) -> str:
        return os.path.join(CONFIG_DIR, f"{self.id}.token")

    @property
    def env_key(self) -> str:
        return self.env_keys[0] if self.env_keys else ""

    def model_env(self) -> str:
        return f"IDUN_{self.id.upper().replace('-', '_')}_MODEL"

    def base_env(self) -> str:
        return f"IDUN_{self.id.upper().replace('-', '_')}_BASE"

    def resolved_base(self) -> str:
        # Azure keeps its established IDUN_BASE name; others use IDUN_<ID>_BASE.
        if self.id == "azure":
            return (os.environ.get("IDUN_BASE")
                    or os.environ.get(self.base_env()) or self.base)
        return os.environ.get(self.base_env(), self.base)

    def resolved_model(self) -> str:
        return os.environ.get(self.model_env(), self.default_model)


# --------------------------------------------------------------------------
# Registry — 12 providers, OpenAI-dialect unless noted
# --------------------------------------------------------------------------

REGISTRY: tuple[Provider, ...] = (
    Provider(
        id="azure",
        label="Azure AI Foundry (NatureLM-Idun)",
        # No tenant baked in: configure with IDUN_BASE / IDUN_PROJECT.
        base="https://<resource>.services.ai.azure.com",
        default_model="model-router",
        env_keys=("IDUN_TOKEN", "AZURE_TOKEN"),
        models=("model-router",),
        notes="Set IDUN_BASE + IDUN_PROJECT; Entra device-code via `idun login`.",
        transport="azure",
    ),
    Provider(
        id="openai",
        label="OpenAI",
        base="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        env_keys=("OPENAI_API_KEY", "OPENAI_TOKEN"),
        models=("gpt-4o-mini", "gpt-4o", "gpt-4.1", "o4-mini"),
    ),
    Provider(
        id="anthropic",
        label="Anthropic Claude",
        base="https://api.anthropic.com/v1",
        default_model="claude-sonnet-4-20250514",
        env_keys=("ANTHROPIC_API_KEY",),
        models=("claude-sonnet-4-20250514", "claude-opus-4-20250514",
                "claude-3-5-haiku-20241022"),
        notes="Native messages API (x-api-key + anthropic-version).",
        transport="anthropic",
    ),
    Provider(
        id="groq",
        label="Groq (LPU, very fast)",
        base="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        env_keys=("GROQ_API_KEY",),
        models=("llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                "mixtral-8x7b-32768"),
        free_tier=True,
    ),
    Provider(
        id="openrouter",
        label="OpenRouter (400+ models)",
        base="https://openrouter.ai/api/v1",
        default_model="meta-llama/llama-3.3-70b-instruct",
        env_keys=("OPENROUTER_API_KEY",),
        models=("meta-llama/llama-3.3-70b-instruct",
                "deepseek/deepseek-chat", "anthropic/claude-sonnet-4"),
        free_tier=True,
    ),
    Provider(
        id="together",
        label="Together AI",
        base="https://api.together.xyz/v1",
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        env_keys=("TOGETHER_API_KEY",),
        models=("meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "Qwen/Qwen2.5-72B-Instruct-Turbo"),
    ),
    Provider(
        id="deepseek",
        label="DeepSeek",
        base="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        env_keys=("DEEPSEEK_API_KEY",),
        models=("deepseek-chat", "deepseek-reasoner"),
    ),
    Provider(
        id="mistral",
        label="Mistral AI",
        base="https://api.mistral.ai/v1",
        default_model="mistral-large-latest",
        env_keys=("MISTRAL_API_KEY",),
        models=("mistral-large-latest", "mistral-small-latest",
                "open-mistral-nemo"),
    ),
    Provider(
        id="gemini",
        label="Google Gemini (OpenAI-compat)",
        base="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.0-flash",
        env_keys=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        models=("gemini-2.0-flash", "gemini-2.5-pro"),
        free_tier=True,
    ),
    Provider(
        id="xai",
        label="xAI Grok",
        base="https://api.x.ai/v1",
        default_model="grok-3",
        env_keys=("XAI_API_KEY", "GROK_API_KEY"),
        models=("grok-3", "grok-3-mini"),
    ),
    Provider(
        id="hf",
        label="Hugging Face Inference",
        base="https://api-inference.huggingface.co/models",
        default_model="microsoft/phi-3-mini-4k-instruct",
        env_keys=("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
        models=("microsoft/phi-3-mini-4k-instruct",),
        free_tier=True,
        needs_key=False,
        notes="Anonymous access works but is rate-limited.",
        transport="hf",
    ),
    Provider(
        id="ollama",
        label="Ollama (local, no key)",
        base="http://127.0.0.1:11434/v1",
        default_model="llama3.2",
        env_keys=(),
        models=("llama3.2", "qwen2.5", "phi4"),
        free_tier=True,
        needs_key=False,
        notes="Requires a local `ollama serve`.",
    ),
    Provider(
        id="local",
        label="Local OpenAI-compatible (llama.cpp / vLLM)",
        base="http://127.0.0.1:8080/v1",
        default_model="local-model",
        env_keys=("LOCAL_API_KEY",),
        needs_key=False,
        free_tier=True,
        notes="Point IDUN_LOCAL_BASE at any OpenAI-compatible server.",
    ),
)

_BY_ID = {p.id: p for p in REGISTRY}


def list_providers() -> tuple[Provider, ...]:
    return REGISTRY


def get_provider(pid: str) -> Provider:
    key = (pid or "").strip().lower()
    # accept legacy alias
    if key == "github":
        key = "openai"
    if key not in _BY_ID:
        raise ValueError(
            f"unknown provider {pid!r}. Known: {', '.join(sorted(_BY_ID))}")
    return _BY_ID[key]


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------


def resolve_credential(p: Provider) -> str:
    """Return the API key for a provider from env, then ~/.idun/<id>.token."""
    for key in p.env_keys:
        val = os.environ.get(key)
        if val:
            return val.strip()
    try:
        with open(p.token_file, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def save_credential(p: Provider, token: str) -> str:
    """Persist a provider key to ~/.idun/<id>.token with 0600 perms.

    The file is created atomically with mode 0o600 via os.open(O_CREAT|O_EXCL),
    so there is never a window where the token sits on disk with the process
    umask (typically 0644) before a separate chmod. A missing/permissive
    ~/.idun is tightened to 0700; failure there is non-fatal because the file
    itself is already owner-only.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass
    fd = os.open(p.token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(token.strip())
    except BaseException:
        os.unlink(p.token_file)
        raise
    return p.token_file


def credential_status(p: Provider) -> str:
    """Human-readable credential state: env / file / none / n-a."""
    for key in p.env_keys:
        if os.environ.get(key):
            return f"env:{key}"
    if os.path.exists(p.token_file):
        return "file"
    return "none" if p.needs_key else "not-required"


# --------------------------------------------------------------------------
# Transports
# --------------------------------------------------------------------------


def _require_http_url(url: str) -> str:
    """Reject anything but http(s).

    Base URLs come from the environment (IDUN_<ID>_BASE), so a hostile or
    mistyped value could otherwise make urlopen() read local files via
    `file://` — while an Authorization header carrying the API key is
    attached to the request. Fail closed instead.
    """
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(
            f"refusing non-HTTP(S) endpoint {url!r} (scheme {scheme or 'none'!r}); "
            "check your IDUN_*_BASE configuration")
    return url


def _sanitize_error_body(body: str) -> str:
    """Strip likely secrets from a provider error response before logging.

    Some providers echo the Authorization header or the API key back in a 4xx/
    5xx body. That text ends up in exception messages, logs and CI output, so
    redact anything that looks like a credential before it leaves this module.
    """
    import re
    # Bearer tokens and common key shapes (sk-, pypi-, hf_, etc.)
    body = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+", r"\1<redacted>", body)
    body = re.sub(r"(?i)\b(sk|pk|api[_-]?key|token|secret)[=:\s]+[^\s\"',}]+",
                  r"\1=<redacted>", body)
    body = re.sub(r"\bpypi-[A-Za-z0-9._\-]{8,}", "<redacted>", body)
    return body


def _post_json(url: str, body: dict, headers: dict, timeout: int) -> dict:
    _require_http_url(url)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers,
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = _sanitize_error_body(
            e.read().decode("utf-8", "replace")[:400])
        raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach {url}: {e.reason}") from e


def _call_openai(p: Provider, prompt: str, model: str, token: str, *,
                 system: str = "", temperature: float = 0.7,
                 max_tokens: int = 1024, timeout: int = 120) -> dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature}
    return _post_json(f"{p.resolved_base().rstrip('/')}/chat/completions",
                      body, headers, timeout)


def _call_anthropic(p: Provider, prompt: str, model: str, token: str, *,
                    system: str = "", temperature: float = 0.7,
                    max_tokens: int = 1024, timeout: int = 120) -> dict:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": token,
        "anthropic-version": "2023-06-01",
    }
    body = {"model": model, "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    return _post_json(f"{p.resolved_base().rstrip('/')}/messages",
                      body, headers, timeout)


def _call_hf(p: Provider, prompt: str, model: str, token: str, *,
             system: str = "", temperature: float = 0.7,
             max_tokens: int = 1024, timeout: int = 120) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # HF Inference API has no system-message field. Prepend the system prompt
    # to the user input; this is approximate but keeps the instruction visible
    # to models whose chat template expects a leading system turn.
    inputs = prompt
    if system:
        inputs = f"{system}\n\n{prompt}"
    body = {"inputs": inputs,
            "parameters": {"max_new_tokens": max_tokens,
                           "temperature": temperature,
                           "return_full_text": False}}
    return _post_json(f"{p.resolved_base().rstrip('/')}/{model}",
                      body, headers, timeout)


def _extract_text(transport: str, data: object) -> str:
    """Normalize the wildly different response shapes into plain text."""
    if transport == "anthropic":
        blocks = data.get("content", []) if isinstance(data, dict) else []
        return "".join(b.get("text", "") for b in blocks
                       if isinstance(b, dict))
    if transport == "hf":
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            gen = data.get("generated_text")
            if isinstance(gen, dict):
                return gen.get("content") or gen.get("text") or ""
            return str(gen or "")
        return str(data or "")
    # openai dialect
    if isinstance(data, dict):
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return json.dumps(data, ensure_ascii=False)[:400]
    return str(data)


def _extract_usage(transport: str, data: object) -> tuple[int, int]:
    if not isinstance(data, dict):
        return 0, 0
    if transport == "anthropic":
        u = data.get("usage") or {}
        return int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0))
    u = data.get("usage") or {}
    return int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))


_TRANSPORTS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "hf": _call_hf,
}


def complete(pid: str, prompt: str, *, model: str = "", system: str = "",
             temperature: float = 0.7, max_tokens: int = 1024,
             timeout: int = 120) -> Completion:
    """Send one prompt to a provider and return a normalized Completion.

    Raises RuntimeError on missing credentials or transport failure.
    """
    p = get_provider(pid)
    model = model or p.resolved_model()
    token = resolve_credential(p)
    if p.needs_key and not token:
        env_hint = p.env_key or "the provider key"
        raise RuntimeError(
            f"{p.id}: no credential. Set {env_hint} or run "
            f"`idun login --provider {p.id}`.")

    if p.transport == "azure":
        # Azure Foundry keeps its own client (tool-agent trace, Entra auth).
        from idun.client import IdunClient  # local import: heavier deps
        res = IdunClient().complete(prompt, max_output_tokens=max_tokens)
        return Completion(text=res.text, model=model, provider=p.id,
                          raw={"steps": len(getattr(res, "steps", []))})

    caller = _TRANSPORTS.get(p.transport)
    if caller is None:
        raise RuntimeError(f"{p.id}: unsupported transport {p.transport!r}")

    started = time.time()
    data = caller(p, prompt, model, token, system=system,
                  temperature=temperature, max_tokens=max_tokens,
                  timeout=timeout)
    latency = int((time.time() - started) * 1000)
    ptok, ctok = _extract_usage(p.transport, data)
    return Completion(
        text=_extract_text(p.transport, data).strip(),
        model=model, provider=p.id, prompt_tokens=ptok,
        completion_tokens=ctok, latency_ms=latency,
        raw=data if isinstance(data, dict) else {},
    )


def default_provider() -> str:
    """Active provider id: IDUN_PROVIDER, legacy IDUN_BACKEND, else azure."""
    return (os.environ.get("IDUN_PROVIDER")
            or os.environ.get("IDUN_BACKEND")
            or "azure").strip().lower()


__all__ = [
    "Provider", "Completion", "REGISTRY", "list_providers", "get_provider",
    "resolve_credential", "save_credential", "credential_status", "complete",
    "default_provider", "CONFIG_DIR", "replace",
]

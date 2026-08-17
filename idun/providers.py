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

    def to_dict(self) -> dict:
        """A JSON-serialisable view (raw may be large; see ``raw_lite``)."""
        d = {
            "provider": self.provider,
            "model": self.model,
            "text": self.text,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Completion":
        """Reconstruct from ``to_dict`` output (raw is dropped)."""
        return cls(
            text=d.get("text", ""),
            model=d.get("model", ""),
            provider=d.get("provider", ""),
            prompt_tokens=int(d.get("prompt_tokens", 0)),
            completion_tokens=int(d.get("completion_tokens", 0)),
            latency_ms=int(d.get("latency_ms", 0)),
        )


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
        # Env wins over ~/.idun/config.toml over the registry default.
        from . import config as _cfg
        if self.id == "azure":
            env = os.environ.get("IDUN_BASE") or os.environ.get(self.base_env())
            if env:
                return env
        else:
            env = os.environ.get(self.base_env())
            if env:
                return env
        cfg = _cfg.config_provider_base(self.id)
        if cfg:
            return cfg
        return self.base

    def resolved_model(self) -> str:
        # Env wins over ~/.idun/config.toml over the registry default.
        from . import config as _cfg
        env = os.environ.get(self.model_env())
        if env:
            return env
        cfg = _cfg.config_provider_model(self.id)
        if cfg:
            return cfg
        return self.default_model


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
        id="nous",
        label="Nous Research (Hermes)",
        base="https://api.nousresearch.com/v1",
        default_model="hermes-4-70b",
        env_keys=("NOUS_API_KEY",),
        models=("hermes-4-70b", "hermes-4-405b", "hermes-3-llama-3.1-405b",
                "hermes-3-llama-3.1-8b", "deephermes-3-mistral-24b-preview"),
        notes="OpenAI-compatible chat/completions; key from portal.nousresearch.com. "
               "Free tier: hermes-3-llama-3.1-8b, deephermes-3-mistral-24b-preview.",
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
    Provider(
        id="perplexity",
        label="Perplexity Sonar (web-grounded)",
        base="https://api.perplexity.ai",
        default_model="sonar",
        env_keys=("PERPLEXITY_API_KEY",),
        models=("sonar", "sonar-pro", "sonar-reasoning", "sonar-reasoning-pro"),
        notes="OpenAI-compatible; answers are web-grounded by default.",
    ),
    Provider(
        id="fireworks",
        label="Fireworks AI",
        base="https://api.fireworks.ai/inference/v1",
        default_model="accounts/fireworks/models/llama-v3p3-70b-instruct",
        env_keys=("FIREWORKS_API_KEY",),
        models=(
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/llama-4-scout-instruct-basic",
            "accounts/fireworks/models/deepseek-r1",
        ),
    ),
    Provider(
        id="novita",
        label="Novita AI",
        base="https://api.novita.ai/v3/openai",
        default_model="meta-llama/llama-3.3-70b-instruct",
        env_keys=("NOVITA_API_KEY",),
        models=(
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-v3-turbo",
            "qwen/qwen2.5-72b-instruct",
        ),
        notes="OpenAI-compatible; broad open-model catalogue.",
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
    """Return the API key for a provider.

    Resolution order: env key -> ``~/.idun/<id>.token`` file ->
    ``[<id>] api_key`` in config.toml -> **OS keyring** (opt-in, secondary).
    The token file stays the preferred secret store; the keyring is consulted
    only as a last resort when enabled, so there is never a surprise about
    where a secret lives.
    """
    for key in p.env_keys:
        val = os.environ.get(key)
        if val:
            return val.strip()
    try:
        with open(p.token_file, encoding="utf-8") as fh:
            tok = fh.read().strip()
            if tok:
                return tok
    except OSError:
        pass
    from . import config as _cfg
    cfg_key = _cfg.config_provider_key(p.id)
    if cfg_key:
        return cfg_key
    # opt-in OS keyring (secondary, non-fatal)
    try:
        from .keyring_store import load_keyring
        kr = load_keyring(p)
        if kr:
            return kr
    except Exception:
        pass
    return ""


def save_credential(p: Provider, token: str) -> str:
    """Persist a provider key to ~/.idun/<id>.token with 0600 perms.

    The file is created atomically with mode 0o600 via os.open(O_CREAT|O_EXCL),
    so there is never a window where the token sits on disk with the process
    umask (typically 0644) before a separate chmod. A missing/permissive
    ~/.idun is tightened to 0700; failure there is non-fatal because the file
    itself is already owner-only.

    When the OS keyring backend is opted in, the same token is also mirrored to
    the keyring (best-effort; a keyring failure never fails the file write).
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
    # optional mirror to the OS keyring (non-fatal)
    try:
        from .keyring_store import store_keyring
        store_keyring(p, token)
    except Exception:
        pass
    return p.token_file


def credential_status(p: Provider) -> str:
    """Human-readable credential state: env / file / keyring / none / n-a."""
    for key in p.env_keys:
        if os.environ.get(key):
            return f"env:{key}"
    if os.path.exists(p.token_file):
        return "file"
    try:
        from .keyring_store import keyring_status
        if keyring_status(p):
            return "keyring"
    except Exception:
        pass
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


# --------------------------------------------------------------------------
# Response cache (v0.4) — content-addressed, opt-out via IDUN_NO_CACHE.
# --------------------------------------------------------------------------

CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
CACHE_MAX_AGE_S = int(os.environ.get("IDUN_CACHE_MAX_AGE", "86400"))  # 24h


def _cache_key(pid: str, model: str, prompt: str, system: str,
               history: list | None, temperature: float, max_tokens: int) -> str:
    import hashlib
    payload = json.dumps(
        {
            "pid": pid, "model": model, "prompt": prompt, "system": system,
            "history": history or [], "temperature": temperature,
            "max_tokens": max_tokens,
        },
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.json")


def cache_get(key: str):
    """Return the cached Completion dict for ``key`` or None (miss/expired)."""
    if os.environ.get("IDUN_NO_CACHE"):
        return None
    path = _cache_path(key)
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    age = time.time() - rec.get("ts", 0)
    if age > CACHE_MAX_AGE_S:
        return None
    return rec.get("data")


def cache_put(key: str, data: dict) -> None:
    """Persist a Completion-like dict under ``key`` (best-effort)."""
    if os.environ.get("IDUN_NO_CACHE"):
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(key), "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "data": data}, fh)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Retry with backoff (v0.4) — honors Retry-After, capped exponential + jitter.
# --------------------------------------------------------------------------

_RETRYABLE = {429, 500, 502, 503, 504}


def _backoff_sleep(attempt: int, retry_after: float | None) -> float:
    """Seconds to wait before retry ``attempt`` (0-based)."""
    if retry_after is not None:
        return retry_after
    # exponential 1,2,4,8... capped at 30s, with up to 250ms jitter
    import random
    base = min(30.0, 2.0 ** attempt)
    return base + random.uniform(0, 0.25)


def with_retry(fn, *, retries: int = 3):
    """Call ``fn``; on retryable HTTPError back off and retry (honors Retry-After).

    Non-retryable errors (4xx != 429, transport failure) propagate immediately.
    Returns whatever ``fn`` returns.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code not in _RETRYABLE or attempt == retries:
                raise
            retry_after = None
            try:
                ra = e.headers.get("Retry-After") if e.headers else None
                if ra:
                    retry_after = float(ra)
            except (TypeError, ValueError):
                retry_after = None
            last_exc = e
            time.sleep(_backoff_sleep(attempt, retry_after))
    # unreachable when retries >= 0, but keep mypy happy
    raise last_exc or RuntimeError("retry loop exited without result")


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
                 max_tokens: int = 1024, timeout: int = 120,
                 history: list[dict] | None = None) -> dict:
    messages = _build_messages(system, prompt, history)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature}
    return _post_json(f"{p.resolved_base().rstrip('/')}/chat/completions",
                      body, headers, timeout)


def _stream_openai(p: Provider, model: str, token: str, messages: list[dict],
                   temperature: float, max_tokens: int, timeout: int):
    """Stream a chat completion over SSE, yielding text deltas.

    Yields ``str`` chunks as they arrive; on transport failure raises
    RuntimeError. Parses the OpenAI ``data: {json}`` event stream and stops at
    the ``[DONE]`` sentinel. Insecure (non-http(s)) bases are rejected by
    ``_require_http_url`` before any connection is made.
    """
    url = f"{p.resolved_base().rstrip('/')}/chat/completions"
    _require_http_url(url)
    headers = {"Content-Type": "application/json",
               "Accept": "text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {"model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature,
            "stream": True}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            buf = ""
            while True:
                chunk = resp.read(1)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", "replace")
                # SSE frames are separated by a blank line
                while "\n\n" in buf:
                    frame, buf = buf.split("\n\n", 1)
                    for line in frame.splitlines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload = line[len("data:"):].strip()
                        if payload == "[DONE]":
                            return
                        try:
                            obj = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if obj.get("error"):
                            raise RuntimeError(
                                f"stream error: {obj['error']}")
                        try:
                            delta = obj["choices"][0]["delta"]["content"] or ""
                        except (KeyError, IndexError, TypeError):
                            delta = ""
                        if delta:
                            yield delta
    except urllib.error.HTTPError as e:
        detail = _sanitize_error_body(
            e.read().decode("utf-8", "replace")[:400])
        raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach {url}: {e.reason}") from e


def _call_anthropic(p: Provider, prompt: str, model: str, token: str, *,
                    system: str = "", temperature: float = 0.7,
                    max_tokens: int = 1024, timeout: int = 120,
                    history: list[dict] | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": token,
        "anthropic-version": "2023-06-01",
    }
    messages = _build_messages(system, prompt, history, drop_system=True)
    body = {"model": model, "max_tokens": max_tokens,
            "temperature": temperature, "messages": messages}
    if system:
        body["system"] = system
    return _post_json(f"{p.resolved_base().rstrip('/')}/messages",
                      body, headers, timeout)


def _call_hf(p: Provider, prompt: str, model: str, token: str, *,
             system: str = "", temperature: float = 0.7,
             max_tokens: int = 1024, timeout: int = 120,
             history: list[dict] | None = None) -> dict:
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


def _build_messages(system: str, prompt: str,
                    history: list[dict] | None,
                    drop_system: bool = False) -> list[dict]:
    """Assemble the message list from (optional) system + history + new user turn.

    ``history`` is a list of ``{"role": ..., "content": ...}`` dicts exactly as
    returned by an OpenAI-style API, so a prior conversation can be resumed by
    passing the stored ``messages`` back in. The new user ``prompt`` is always
    appended last. When ``drop_system`` is set (Anthropic) the system turn is
    omitted here because the caller passes it as a top-level field instead.
    """
    messages: list[dict] = []
    if system and not drop_system:
        messages.append({"role": "system", "content": system})
    if history:
        for m in history:
            if isinstance(m, dict) and "role" in m and "content" in m:
                role = m["role"]
                # normalize roles the providers understand
                if role not in ("system", "user", "assistant"):
                    role = "user"
                messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": prompt})
    return messages


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
             timeout: int = 120, history: list[dict] | None = None,
             stream: bool = False, no_cache: bool = False,
             retries: int = 3):
    """Send one prompt to a provider and return a normalized Completion.

    ``history`` is an optional list of prior ``{"role", "content"}`` turns; when
    given the conversation is resumed instead of starting fresh.

    With ``stream=True`` the function returns a generator instead of a
    Completion: it yields text chunks (``str``) as they arrive over SSE. Only
    the ``openai`` transport supports streaming today; every other transport
    falls back to a single-chunk yield of the full response so callers can rely
    on the same interface. Streamed responses are never cached.

    Caching: identical (provider, model, prompt, system, history, temperature,
    max_tokens) requests hit ``~/.idun/cache`` for up to ``IDUN_CACHE_MAX_AGE``
    seconds. Pass ``no_cache=True`` or set ``IDUN_NO_CACHE`` to bypass.
    Retries: on HTTP 429/5xx the call backs off (honoring ``Retry-After``), up
    to ``retries`` attempts, before giving up.

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
        text = res.text
        if stream:
            def _one():
                yield text
            return _one()
        return Completion(text=text, model=model, provider=p.id,
                          raw={"steps": len(getattr(res, "steps", []))})

    # Cache lookup (non-stream only; streaming is not cached).
    cache_key = None
    if not stream and not no_cache:
        cache_key = _cache_key(p.id, model, prompt, system,
                               history, temperature, max_tokens)
        cached = cache_get(cache_key)
        if cached is not None:
            return Completion(
                text=cached.get("text", ""),
                model=cached.get("model", model),
                provider=cached.get("provider", p.id),
                prompt_tokens=cached.get("prompt_tokens", 0),
                completion_tokens=cached.get("completion_tokens", 0),
                latency_ms=cached.get("latency_ms", 0),
                raw=cached.get("raw", {}) or {},
            )

    if stream and p.transport == "openai":
        messages = _build_messages(system, prompt, history)
        return _stream_openai(p, model, token, messages, temperature,
                               max_tokens, timeout)

    caller = _TRANSPORTS.get(p.transport)
    if caller is None:
        raise RuntimeError(f"{p.id}: unsupported transport {p.transport!r}")

    started = time.time()
    # Retry on transient 429/5xx (honors Retry-After) before surfacing failure.
    data = with_retry(
        lambda: caller(p, prompt, model, token, system=system,
                       temperature=temperature, max_tokens=max_tokens,
                       timeout=timeout, history=history),
        retries=retries,
    )
    latency = int((time.time() - started) * 1000)
    ptok, ctok = _extract_usage(p.transport, data)
    completion = Completion(
        text=_extract_text(p.transport, data).strip(),
        model=model, provider=p.id, prompt_tokens=ptok,
        completion_tokens=ctok, latency_ms=latency,
        raw=data if isinstance(data, dict) else {},
    )
    if cache_key is not None:
        cache_put(cache_key, {
            "text": completion.text, "model": completion.model,
            "provider": completion.provider,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "latency_ms": completion.latency_ms, "raw": completion.raw,
        })
    if not stream:
        return completion
    # non-streaming transports: expose the same generator interface so callers
    # can always iterate regardless of which provider answered.
    def _single():
        yield completion.text
    return _single()


def extract_last_user(messages: list) -> str:
    """Pull the last user turn out of a Foundry-style message-list.

    Accepts either a plain string or a list of ``{"role", "content"}`` dicts
    (content may be a string or a list of ``{"type": "input_text",
    "text": ...}`` blocks). Returns the last user text, or the raw string
    form as a fallback. Used by the legacy ``IdunClient.complete_messages``
    path, which flattens multi-turn lists to a single prompt for the
    single-turn external backends.
    """
    if isinstance(messages, str):
        return messages
    if not isinstance(messages, list):
        return str(messages)
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "input_text":
                    return c.get("text", "")
    # fallback: first available text
    return str(messages)


def default_provider() -> str:
    """Active provider id: IDUN_PROVIDER, legacy IDUN_BACKEND, else azure."""
    return (os.environ.get("IDUN_PROVIDER")
            or os.environ.get("IDUN_BACKEND")
            or "azure").strip().lower()


def complete_chain(chain: list[str], prompt: str, *, model: str = "",
                   system: str = "", temperature: float = 0.7,
                   max_tokens: int = 1024, timeout: int = 120,
                   history: list[dict] | None = None,
                   no_cache: bool = False, retries: int = 1) -> Completion:
    """Try providers in order, falling back on failure.

    Unlike a single ``complete()`` call, this walks ``chain`` (a list of
    provider ids). A provider that raises a retryable error (HTTP 429/5xx),
    an auth error (no credential / 401), or any transport failure is skipped
    and the next link is tried. The first provider to return a Completion
    wins; its ``raw`` is annotated with ``_chain`` (the full tried order) and
    ``_served_by`` (which link answered) so callers can report it.

    Raises RuntimeError only if every link failed (the message lists each
    failure). ``retries`` per link is kept low (default 1) because the chain
    itself is the resilience mechanism.
    """
    errors: list[str] = []
    for pid in chain:
        try:
            comp = complete(
                pid, prompt, model=model, system=system,
                temperature=temperature, max_tokens=max_tokens,
                timeout=timeout, history=history, no_cache=no_cache,
                retries=retries,
            )
            raw = dict(comp.raw) if isinstance(comp.raw, dict) else {}
            raw["_chain"] = list(chain)
            raw["_served_by"] = pid
            return Completion(
                text=comp.text, model=comp.model, provider=comp.provider,
                prompt_tokens=comp.prompt_tokens,
                completion_tokens=comp.completion_tokens,
                latency_ms=comp.latency_ms, raw=raw,
            )
        except (RuntimeError, ValueError) as e:
            errors.append(f"{pid}: {e}")
            continue
    raise RuntimeError("all chain links failed: " + " | ".join(errors))


# -------------------------------------------------------------------------
# Model discovery (v0.5) — live GET /v1/models, cached on disk.
# -------------------------------------------------------------------------

MODELS_CACHE_DIR = os.path.join(CONFIG_DIR, "models")
MODELS_CACHE_MAX_AGE_S = int(os.environ.get("IDUN_MODELS_CACHE_MAX_AGE",
                                             "86400"))  # 24h


def _models_cache_path(pid: str) -> str:
    return os.path.join(MODELS_CACHE_DIR, f"{pid}.json")


def _models_cache_get(pid: str):
    if os.environ.get("IDUN_NO_MODELS_CACHE"):
        return None
    try:
        with open(_models_cache_path(pid), encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    if time.time() - rec.get("ts", 0) > MODELS_CACHE_MAX_AGE_S:
        return None
    return rec.get("models")


def _models_cache_put(pid: str, models: list[str]) -> None:
    if os.environ.get("IDUN_NO_MODELS_CACHE"):
        return
    try:
        os.makedirs(MODELS_CACHE_DIR, exist_ok=True)
        with open(_models_cache_path(pid), "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "models": models}, fh)
    except OSError:
        pass


def discover_models(pid: str, *, timeout: int = 30, force: bool = False) -> list[str]:
    """Return live model ids for a provider via ``GET {base}/models``.

    Results are cached under ``~/.idun/models/<pid>.json`` for 24h (override
    with ``IDUN_MODELS_CACHE_MAX_AGE`` or disable with
    ``IDUN_NO_MODELS_CACHE``). On any failure (no network, non-OpenAI
    transport, auth error) the registry's hardcoded ``models`` tuple is
    returned so callers always get something usable.
    """
    p = get_provider(pid)
    if not force:
        cached = _models_cache_get(pid)
        if cached is not None:
            return cached
    if p.transport not in ("openai", "azure"):
        # HF/anthropic have no uniform /models endpoint we can rely on
        return list(p.models)
    token = resolve_credential(p)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{p.resolved_base().rstrip('/')}/models"
    try:
        data = _get_json(url, headers, timeout)
    except (RuntimeError, ValueError):
        return list(p.models)
    ids: list[str] = []
    items = data.get("data") if isinstance(data, dict) else None
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and it.get("id"):
                ids.append(str(it["id"]))
    if not ids:
        return list(p.models)
    _models_cache_put(pid, ids)
    return ids


def _get_json(url: str, headers: dict, timeout: int) -> dict:
    _require_http_url(url)
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = _sanitize_error_body(
            e.read().decode("utf-8", "replace")[:400])
        raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach {url}: {e.reason}") from e


__all__ = [
    "Provider", "Completion", "REGISTRY", "list_providers", "get_provider",
    "resolve_credential", "save_credential", "credential_status", "complete",
    "complete_chain", "discover_models", "default_provider", "CONFIG_DIR",
    "replace",
]

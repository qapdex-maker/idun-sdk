"""Idun SDK — thin client + CLI for Azure AI Foundry agent NatureLM-Idun-5-MoE.

Stdlib-only (urllib, no httpx / azure.identity) so it runs on Termux/Android.
Mirrors the working request shape discovered during integration:
  POST {base}/api/projects/{project}/agents/{agent}/endpoint/protocols/openai/responses?api-version={ver}
  body: {"model": "model-router", "input": "<prompt string>", "max_output_tokens": N}
  auth: Entra Bearer token (FOUNDRY_TOKEN), scope https://ai.azure.com/.default

Returns both the final text AND the agent trajectory ("steps"):
  - kind=reasoning  -> assistant plan / reasoning text
  - kind=tool        -> web_search call: {tool, query, status}
This is what makes Idun a visible tool-agent, not a chatbot wheel.
"""
from __future__ import annotations

import asyncio
import json
import os
import time

from . import providers as _pr
from .providers import get_provider, resolve_credential
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

# --- Azure Foundry configuration ---------------------------------------
# NO tenant-specific values are baked into this package. Every field is read
# from the environment at call time; the placeholders below only document the
# expected shape. Configure your own resource with:
#   export IDUN_BASE=https://<your-resource>.services.ai.azure.com
#   export IDUN_PROJECT=<your-project>
#   export IDUN_AGENT=<your-agent>
#   export IDUN_TENANT=<your-tenant-guid>   # or "organizations" / "common"
FOUNDRY_BASE_PLACEHOLDER = "https://<resource>.services.ai.azure.com"
FOUNDRY_PROJECT_PLACEHOLDER = "<project>"
FOUNDRY_AGENT_DEFAULT = "NatureLM-Idun-5-MoE"
FOUNDRY_API_VERSION_DEFAULT = "2025-05-15-preview"
FOUNDRY_SCOPE = "https://ai.azure.com/.default"
# Multi-tenant endpoint by default: works for any tenant, leaks none.
FOUNDRY_TENANT_DEFAULT = "organizations"
TOKEN_FILE = os.path.join(os.path.expanduser("~"), "foundry_token.txt")


def _config_defaults() -> dict:
    """Read [defaults] from ~/.idun/config.toml (tenant-agnostic, no hard-coded resource)."""
    try:
        from . import config as _cfg

        cfg = _cfg.load_config()
        return cfg.get("defaults", {}) or {}
    except Exception:
        return {}


def foundry_base() -> str:
    """Foundry resource base URL: IDUN_BASE env > config.toml > empty (unset)."""
    env = (os.environ.get("IDUN_BASE") or "").strip().rstrip("/")
    if env:
        return env
    return (_config_defaults().get("idun_base") or "").strip().rstrip("/")


def foundry_project() -> str:
    """Foundry project name: IDUN_PROJECT env > config.toml > empty (unset)."""
    env = (os.environ.get("IDUN_PROJECT") or "").strip()
    if env:
        return env
    return (_config_defaults().get("idun_project") or "").strip()


def foundry_agent() -> str:
    """Foundry agent name: IDUN_AGENT env > config.toml > default."""
    env = (os.environ.get("IDUN_AGENT") or "").strip()
    if env:
        return env
    return (_config_defaults().get("idun_agent") or FOUNDRY_AGENT_DEFAULT).strip()


def foundry_tenant() -> str:
    """Entra tenant from IDUN_TENANT, else the multi-tenant endpoint."""
    return (os.environ.get("IDUN_TENANT") or FOUNDRY_TENANT_DEFAULT).strip()


# Backwards-compatible aliases (deprecated, no longer tenant-specific).
FOUNDRY_BASE_DEFAULT = FOUNDRY_BASE_PLACEHOLDER
FOUNDRY_PROJECT_DEFAULT = FOUNDRY_PROJECT_PLACEHOLDER
FOUNDRY_TENANT = FOUNDRY_TENANT_DEFAULT


@dataclass
class Step:
    kind: str  # "reasoning" | "tool" | "message"
    text: str = ""
    tool: str = ""
    query: str = ""
    status: str = ""
    id: str = ""


@dataclass
class IdunResult:
    text: str
    steps: List[Step] = field(default_factory=list)
    model: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Machine-readable snapshot of the whole result (for re-ingest/CI)."""
        return {
            "model": self.model,
            "text": self.text,
            "steps": [s.__dict__ for s in self.steps],
            "raw": self.raw,
        }

    def to_json(self, indent: int = 2) -> str:
        """Compact JSON of the full trajectory (steps + final answer + raw)."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Human-readable trace doc: header, step list, final answer."""
        lines = [f"# Idun Trace — {self.model or 'unknown model'}", ""]
        lines.append(f"**Steps:** {len(self.steps)}")
        lines.append("")
        lines.append("---")
        for i, s in enumerate(self.steps, 1):
            if s.kind == "tool":
                lines.append(f"{i}. **TOOL** `{s.tool}` — {s.status}")
                if s.query:
                    lines.append(f"   - query: `{s.query}`")
            else:
                label = "REASON" if s.kind == "reasoning" else "MSG"
                body = s.text.strip().replace("\n", " ")
                lines.append(f"{i}. **{label}** {body[:280]}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Final Answer")
        lines.append("")
        lines.append(self.text.strip())
        return "\n".join(lines)


def diff_traces(a: IdunResult, b: IdunResult) -> dict:
    """Compare two agent trajectories (side-by-side tool-timeline diff).

    Returns a structured dict:
      - n_steps_a / n_steps_b
      - only_a / only_b: tool queries unique to each run
      - shared_queries: tool queries present in both runs
      - text_a_len / text_b_len
      - same_answer: exact final-text match
    Offline, no network.
    """
    qa = {s.query for s in a.steps if s.kind == "tool" and s.query}
    qb = {s.query for s in b.steps if s.kind == "tool" and s.query}
    return {
        "n_steps_a": len(a.steps),
        "n_steps_b": len(b.steps),
        "shared_queries": sorted(qa & qb),
        "only_a": sorted(qa - qb),
        "only_b": sorted(qb - qa),
        "text_a_len": len(a.text),
        "text_b_len": len(b.text),
        "same_answer": a.text.strip() == b.text.strip(),
    }


def format_diff(d: dict, fmt: str = "md") -> str:
    """Render a diff_traces() result as markdown or json."""
    if fmt == "json":
        return json.dumps(d, indent=2, ensure_ascii=False)
    lines = ["# Idun Trace Diff", ""]
    lines.append(f"- Steps A: **{d['n_steps_a']}**  |  Steps B: **{d['n_steps_b']}**")
    lines.append(f"- Final answer identical: **{d['same_answer']}** "
                 f"(len A={d['text_a_len']}, B={d['text_b_len']})")
    lines.append("")
    lines.append(f"## Shared tool queries ({len(d['shared_queries'])})")
    for q in d["shared_queries"]:
        lines.append(f"  - `{q}`")
    lines.append("")
    lines.append(f"## Unique to A ({len(d['only_a'])})")
    for q in d["only_a"]:
        lines.append(f"  - `{q}`")
    lines.append("")
    lines.append(f"## Unique to B ({len(d['only_b'])})")
    for q in d["only_b"]:
        lines.append(f"  - `{q}`")
    return "\n".join(lines)


def _normalize_output(data: dict) -> IdunResult:
    """Convert Foundry Responses output[] into (final_text, steps[])."""
    text = ""
    steps: List[Step] = []
    for o in data.get("output", []):
        otype = o.get("type")
        if otype == "message" and o.get("role") == "assistant":
            t = "".join(c.get("text", "") for c in o.get("content", []) if c.get("type") == "output_text")
            if t:
                text += t + "\n\n"
                steps.append(Step(kind="reasoning", text=t))
        elif otype == "web_search_call":
            action = o.get("action") or {}
            q = action.get("query") or ""
            if action.get("queries"):
                q = action["queries"][0]
            steps.append(Step(kind="tool", tool="web_search", query=q,
                              status=o.get("status", "unknown"), id=o.get("id")))
        elif otype == "message":
            t = "".join(c.get("text", "") for c in o.get("content", []) if c.get("type") == "output_text")
            if t:
                text += t + "\n\n"
                steps.append(Step(kind="message", text=t))
    return IdunResult(text=text.strip(), steps=steps,
                      model=data.get("model", ""), raw=data)


class IdunClient:
    def __init__(
        self,
        token: Optional[str] = None,
        base: Optional[str] = None,
        project: Optional[str] = None,
        agent: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout: int = 600,
        backend: Optional[str] = None,
        hf_token: Optional[str] = None,
        hf_model: Optional[str] = None,
        openai_token: Optional[str] = None,
        openai_model: Optional[str] = None,
        openai_base: Optional[str] = None,
    ) -> None:
        # --- backend selection (multi-backend support) ---
        # The provider registry in providers.py is the single source of truth.
        # There are no aliases: 'github' was removed because it mapped onto the
        # openai provider and its token file (see providers.get_provider).
        self.backend = (backend or os.environ.get("IDUN_BACKEND", "azure")).strip().lower()
        try:
            self._provider = get_provider(self.backend)
        except ValueError:
            valid = ", ".join(sorted(p.id for p in _pr.list_providers()))
            raise ValueError(
                f"IDUN_BACKEND={self.backend!r} invalid; choose one of {valid}") from None
        # external-backend credentials/models (env-overridable). Explicit
        # constructor args win over env over ~/.idun/<id>.token (0600).
        p = self._provider
        if p.id == "hf":
            self.hf_token = hf_token if hf_token is not None else resolve_credential(p)
            self.hf_model = hf_model or os.environ.get("HF_MODEL") or p.resolved_model()
        elif p.id == "openai":
            self.openai_token = openai_token if openai_token is not None else resolve_credential(p)
            self.openai_model = openai_model or os.environ.get("OPENAI_MODEL") or p.resolved_model()
            self.openai_base = openai_base or os.environ.get("OPENAI_BASE") or p.resolved_base()
        # --- azure config: explicit arg > environment > (no tenant default) ---
        self.token = token or os.environ.get("FOUNDRY_TOKEN")
        self.base = (base if base is not None else foundry_base()).rstrip("/")
        self.project = project if project is not None else foundry_project()
        self.agent = agent if agent is not None else foundry_agent()
        self.api_version = (api_version if api_version is not None
                            else os.environ.get("IDUN_API_VERSION")
                            or FOUNDRY_API_VERSION_DEFAULT)
        self.timeout = timeout
        # Fail loudly, and only for the azure backend, when unconfigured.
        if self.backend == "azure" and (not self.base or not self.project):
            raise ValueError(
                "Azure Foundry is not configured. Set your own resource:\n"
                "  export IDUN_BASE=https://<resource>.services.ai.azure.com\n"
                "  export IDUN_PROJECT=<project>\n"
                "  export IDUN_AGENT=<agent>            # optional\n"
                "  export IDUN_TENANT=<tenant-guid>     # optional\n"
                "Or pass base=/project= explicitly. No tenant is bundled with "
                "this package.")

    def _url(self) -> str:
        return (f"{self.base}/api/projects/{self.project}/agents/{self.agent}"
                f"/endpoint/protocols/openai/responses?api-version={self.api_version}")

    def _headers(self) -> dict:
        if not self.token:
            raise RuntimeError("No FOUNDRY_TOKEN set. Run `idun login` or export FOUNDRY_TOKEN.")
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _build_payload(self, prompt: str, max_output_tokens: int = 4096) -> dict:
        """Verified working request shape for the agent-in-URL endpoint.

        Model MUST stay 'model-router' (agent name -> invalid_payload).
        No 'tools' key (agent owns capabilities -> 400 invalid_payload).
        `input` may be a string (single-turn) or a list of message dicts
        (multi-turn, server-side conversation state) — both verified live
        against Foundry (HTTP 200 for both shapes).
        """
        return {
            "model": "model-router",
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }

    def _post_once(self, prompt: str, max_output_tokens: int) -> dict:
        payload = self._build_payload(prompt, max_output_tokens)
        req = urllib.request.Request(
            self._url(), data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(), method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    # Transient server errors that are worth retrying (Foundry returns these
    # intermittently — observed live as bare HTTP 500 with no body). 401 is NOT
    # here: that is a token problem, handled separately by maybe_refresh().
    _RETRYABLE = {500, 502, 503, 429}

    def _post_with_retry(self, prompt: str, max_output_tokens: int,
                         max_attempts: int = 3) -> dict:
        """POST with exponential backoff on transient 5xx / 429.

        A retryable HTTPError sleeps 2**attempt seconds and retries; after
        max_attempts it re-raises with the last body. Non-retryable errors
        (e.g. 400 invalid_payload, 401) propagate immediately.
        """
        last_err: Optional[urllib.error.HTTPError] = None
        for attempt in range(max_attempts):
            try:
                return self._post_once(prompt, max_output_tokens)
            except urllib.error.HTTPError as e:
                if e.code not in self._RETRYABLE or attempt == max_attempts - 1:
                    body = e.read().decode("utf-8", "replace")[:400]
                    raise RuntimeError(f"Foundry HTTP {e.code}: {body}") from e
                last_err = e
                sleep_s = 2 ** attempt
                time.sleep(sleep_s)
        # should be unreachable (loop always raises on last attempt), but keep
        # mypy happy
        raise last_err or RuntimeError("retry loop exited without result")

    def complete(self, prompt: str, max_output_tokens: int = 4096) -> IdunResult:
        """Synchronous completion. Returns final text + agent trajectory.

        Backend dispatch:
          - azure : Foundry agent (token-managed, retries on 5xx/401).
          - hf / openai : external backends, no Foundry token needed.

        The non-azure backends return a flat answer (no tool-agent trajectory),
        so `steps` is empty and `model` is the backend model id.
        """
        if self.backend != "azure":
            comp = _pr.complete(
                self.backend, prompt,
                model=self.hf_model if self.backend == "hf" else self.openai_model,
                max_tokens=max_output_tokens,
                timeout=self.timeout,
                stream=False,
            )
            return IdunResult(text=comp.text, steps=[], model=comp.model, raw={"backend": self.backend})

        from .auth import maybe_refresh  # lazy import keeps install_requires=[]

        # ensure a fresh token before the request
        refreshed = maybe_refresh()
        if refreshed:
            self.token = refreshed

        try:
            data = self._post_with_retry(prompt, max_output_tokens)
        except RuntimeError as exc:
            # RuntimeError from _post_with_retry may wrap a 401 — unwrap and
            # apply the token-rotation retry path.
            # NOTE: do not name this `re` — it shadows the stdlib module and is
            # a trap for any later edit that needs a regex here.
            if "Foundry HTTP 401" in str(exc):
                rotated = maybe_refresh(force=True)
                if rotated:
                    self.token = rotated
                    data = self._post_with_retry(prompt, max_output_tokens)
                else:
                    raise
            else:
                raise
        return _normalize_output(data)

    def complete_messages(self, messages: list, max_output_tokens: int = 4096) -> IdunResult:
        """Complete with a structured message list (server-side multi-turn).

        For non-azure backends the message-list is flattened to its last user
        turn (those backends are single-turn text), preserving the same API.
        """
        if self.backend != "azure":
            prompt = _pr.extract_last_user(messages)
            return self.complete(prompt, max_output_tokens)

        from .auth import maybe_refresh
        refreshed = maybe_refresh()
        if refreshed:
            self.token = refreshed
        try:
            data = self._post_with_retry_messages(messages, max_output_tokens)
        except RuntimeError as re:
            if "Foundry HTTP 401" in str(re):
                rotated = maybe_refresh(force=True)
                if rotated:
                    self.token = rotated
                    try:
                        data = self._post_with_retry_messages(messages, max_output_tokens)
                    except RuntimeError:
                        raise
                else:
                    raise
            else:
                raise
        return _normalize_output(data)

    def _post_once_messages(self, messages: list, max_output_tokens: int) -> dict:
        payload = {
            "model": "model-router",
            "input": messages,
            "max_output_tokens": max_output_tokens,
        }
        req = urllib.request.Request(
            self._url(), data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(), method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def _post_with_retry_messages(self, messages: list, max_output_tokens: int,
                                 max_attempts: int = 3) -> dict:
        last_err = None
        for attempt in range(max_attempts):
            try:
                return self._post_once_messages(messages, max_output_tokens)
            except urllib.error.HTTPError as e:
                if e.code not in self._RETRYABLE or attempt == max_attempts - 1:
                    body = e.read().decode("utf-8", "replace")[:400]
                    raise RuntimeError(f"Foundry HTTP {e.code}: {body}") from e
                last_err = e
                time.sleep(2 ** attempt)
        raise last_err or RuntimeError("retry loop exited without result")

    async def complete_async(self, prompt: str, max_output_tokens: int = 4096) -> IdunResult:
        """Async variant of complete().

        Stdlib-only: the blocking urllib call runs in the default executor so
        the surrounding asyncio loop stays responsive. Non-azure backends are
        dispatched through run_external (same as sync complete).
        """
        if self.backend != "azure":
            loop = asyncio.get_running_loop()
            from functools import partial
            fn = partial(
                _pr.complete, self.backend, prompt,
                model=self.hf_model if self.backend == "hf" else self.openai_model,
                max_tokens=max_output_tokens,
                timeout=self.timeout, stream=False,
            )
            comp = await loop.run_in_executor(None, fn)
            return IdunResult(text=comp.text, steps=[], model=comp.model, raw={"backend": self.backend})

        from .auth import maybe_refresh  # lazy import keeps install_requires=[]

        refreshed = maybe_refresh()
        if refreshed:
            self.token = refreshed

        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(None, self._post_with_retry, prompt, max_output_tokens)
        except RuntimeError as re:
            if "Foundry HTTP 401" in str(re):
                rotated = maybe_refresh(force=True)
                if rotated:
                    self.token = rotated
                    try:
                        data = await loop.run_in_executor(None, self._post_with_retry, prompt, max_output_tokens)
                    except RuntimeError:
                        raise
                else:
                    raise
            else:
                raise
        return _normalize_output(data)


class Conversation:
    """Minimal multi-turn wrapper around IdunClient.

    Uses Foundry's server-side conversation state via a structured message
    list (role/content), NOT a text prefix. Verified live (2026-08-03): Foundry
    accepts a list `input` and tracks multi-turn context from it. Offline-
    friendly: history is plain (role, text) tuples until rendered to messages.

    Usage:
        conv = Conversation(client)
        r1 = conv.ask("What is the capital of France?")
        r2 = conv.ask("And what is its population?")  # sees turn 1
        conv.history  # list of (role, text)
    """

    def __init__(self, client: "IdunClient", max_output_tokens: int = 4096) -> None:
        self.client = client
        self.max_output_tokens = max_output_tokens
        self.history: List[tuple] = []  # (role, text)

    @staticmethod
    def _to_messages(history: list, prompt: str) -> list:
        """Build a Foundry message-list from (role, text) history + new prompt."""
        msgs = []
        for role, text in history:
            ctype = "output_text" if role == "assistant" else "input_text"
            msgs.append({
                "role": role,
                "content": [{"type": ctype, "text": text.strip()}],
            })
        msgs.append({
            "role": "user",
            "content": [{"type": "input_text", "text": prompt.strip()}],
        })
        return msgs

    def ask(self, prompt: str, max_output_tokens: Optional[int] = None) -> IdunResult:
        """Ask a follow-up; records both sides in history. Returns IdunResult."""
        messages = self._to_messages(self.history, prompt)
        res = self.client.complete_messages(messages, max_output_tokens or self.max_output_tokens)
        self.history.append(("user", prompt))
        self.history.append(("assistant", res.text))
        return res

    async def ask_async(self, prompt: str, max_output_tokens: Optional[int] = None) -> IdunResult:
        # sync call in executor keeps stdlib-only; message-list path is sync
        loop = asyncio.get_running_loop()
        messages = self._to_messages(self.history, prompt)
        res = await loop.run_in_executor(
            None, self.client.complete_messages, messages,
            max_output_tokens or self.max_output_tokens)
        self.history.append(("user", prompt))
        self.history.append(("assistant", res.text))
        return res

    def clear(self) -> None:
        self.history.clear()

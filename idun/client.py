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
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

# --- defaults (verified working for qmfi-research-project, 2026-07-25) ---
FOUNDRY_BASE_DEFAULT = "https://qmfi-research-project-resource.services.ai.azure.com"
FOUNDRY_PROJECT_DEFAULT = "qmfi-research-project"
FOUNDRY_AGENT_DEFAULT = "NatureLM-Idun-5-MoE"
FOUNDRY_API_VERSION_DEFAULT = "2025-05-15-preview"
FOUNDRY_SCOPE = "https://ai.azure.com/.default"
FOUNDRY_TENANT = "885f01ab-7364-4484-be0a-231d541c9e7f"
TOKEN_FILE = os.path.join(os.path.expanduser("~"), "foundry_token.txt")


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
        base: str = FOUNDRY_BASE_DEFAULT,
        project: str = FOUNDRY_PROJECT_DEFAULT,
        agent: str = FOUNDRY_AGENT_DEFAULT,
        api_version: str = FOUNDRY_API_VERSION_DEFAULT,
        timeout: int = 600,
    ) -> None:
        self.token = token or os.environ.get("FOUNDRY_TOKEN")
        self.base = base.rstrip("/")
        self.project = project
        self.agent = agent
        self.api_version = api_version
        self.timeout = timeout

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

        Phase 2.5: rotates the Entra token before the call (silent refresh when
        a refresh_token is stored) and retries once on HTTP 401 (expired token).
        Transient 5xx / 429 are retried with backoff (see _post_with_retry).
        """
        from .auth import maybe_refresh  # lazy import keeps install_requires=[]

        # ensure a fresh token before the request
        refreshed = maybe_refresh()
        if refreshed:
            self.token = refreshed

        try:
            data = self._post_with_retry(prompt, max_output_tokens)
        except RuntimeError as re:
            # RuntimeError from _post_with_retry may wrap a 401 — unwrap and
            # apply the token-rotation retry path.
            if "Foundry HTTP 401" in str(re):
                rotated = maybe_refresh(force=True)
                if rotated:
                    self.token = rotated
                    try:
                        data = self._post_with_retry(prompt, max_output_tokens)
                    except RuntimeError as re2:
                        raise
                else:
                    raise
            else:
                raise
        return _normalize_output(data)

    async def complete_async(self, prompt: str, max_output_tokens: int = 4096) -> IdunResult:
        """Async variant of complete().

        Stdlib-only: the blocking urllib call runs in the default executor so
        the surrounding asyncio loop stays responsive (no httpx/aiohttp dep).
        Rotates the token (sync, fast) before the call; transient 5xx/429 use
        backoff; on 401 it retries once after a forced token rotation.
        """
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

    IdunClient.complete() is stateless (each call is an isolated prompt). This
    wrapper keeps a local history and threads it into the next call as a
    structured text prefix, so the agent "remembers" prior turns without
    relying on server-side session state (which the openai/responses endpoint
    here does not expose). Offline-friendly: history is plain strings.

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

    def _render(self, prompt: str) -> str:
        if not self.history:
            return prompt
        parts = ["Previous conversation:"]
        for role, text in self.history:
            parts.append(f"[{role}] {text.strip()}")
        parts.append(f"[user] {prompt.strip()}")
        parts.append("")
        parts.append("Answer the latest [user] message, using the context above.")
        return "\n".join(parts)

    def ask(self, prompt: str, max_output_tokens: Optional[int] = None) -> IdunResult:
        """Ask a follow-up; records both sides in history. Returns IdunResult."""
        full = self._render(prompt)
        res = self.client.complete(full, max_output_tokens or self.max_output_tokens)
        self.history.append(("user", prompt))
        self.history.append(("assistant", res.text))
        return res

    async def ask_async(self, prompt: str, max_output_tokens: Optional[int] = None) -> IdunResult:
        full = self._render(prompt)
        res = await self.client.complete_async(full, max_output_tokens or self.max_output_tokens)
        self.history.append(("user", prompt))
        self.history.append(("assistant", res.text))
        return res

    def clear(self) -> None:
        self.history.clear()

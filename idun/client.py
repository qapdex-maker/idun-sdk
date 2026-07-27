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

    def complete(self, prompt: str, max_output_tokens: int = 4096) -> IdunResult:
        """Synchronous completion. Returns final text + agent trajectory.

        Phase 2.5: rotates the Entra token before the call (silent refresh when
        a refresh_token is stored) and retries once on HTTP 401 (expired token).
        """
        from .auth import maybe_refresh  # lazy import keeps install_requires=[]

        # ensure a fresh token before the request
        refreshed = maybe_refresh()
        if refreshed:
            self.token = refreshed

        try:
            data = self._post_once(prompt, max_output_tokens)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # token may have just expired -> one forced rotation + retry
                rotated = maybe_refresh(force=True)
                if rotated:
                    self.token = rotated
                    try:
                        data = self._post_once(prompt, max_output_tokens)
                    except urllib.error.HTTPError as e2:
                        body = e2.read().decode("utf-8", "replace")[:400]
                        raise RuntimeError(f"Foundry HTTP {e2.code} after token refresh: {body}") from e2
                else:
                    raise
            else:
                body = e.read().decode("utf-8", "replace")[:400]
                raise RuntimeError(f"Foundry HTTP {e.code}: {body}") from e
        return _normalize_output(data)

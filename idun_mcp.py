#!/usr/bin/env python3
"""Idun MCP server (stdio, stdlib-only).

Exposes the NatureLM-Idun-5-MoE agent as MCP tools so other agents/clients
can call it. No FastMCP / httpx / pydantic: implements the minimal MCP
JSON-RPC-over-stdio wire contract with only the standard library.

Tools:
  idun_chat(prompt) -> final answer text
  idun_trace(prompt) -> full agent trajectory (steps + text)

Auth: reads FOUNDRY_TOKEN / FOUNDRY_RESOURCE / FOUNDRY_AGENT from the
environment (same as the CLI). Entra device-code login is the caller's job
(`idun login`); this server only relays.

Run:
  python3 idun_mcp.py            # stdio MCP server
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idun.client import IdunClient


TOOLS = [
    {
        "name": "idun_chat",
        "description": "Ask the NatureLM-Idun-5-MoE agent a question and return the final answer text.",
        "inputSchema": {
            "type": "object",
            "properties": {"prompt": {"type": "string",
                                      "description": "The user prompt for the Idun agent."}},
            "required": ["prompt"],
        },
    },
    {
        "name": "idun_trace",
        "description": ("Ask the Idun agent and return the FULL trajectory (reasoning + "
                        "tool calls) plus the final text — for auditable, visible tool-agent use."),
        "inputSchema": {
            "type": "object",
            "properties": {"prompt": {"type": "string",
                                      "description": "The user prompt for the Idun agent."}},
            "required": ["prompt"],
        },
    },
    {
        "name": "idun_export",
        "description": ("Run a prompt and return the full agent trajectory as JSON or "
                        "human-readable Markdown (for archival / audit)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The user prompt."},
                "format": {"type": "string", "enum": ["json", "md"], "default": "json",
                           "description": "Output format."},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "idun_diff",
        "description": ("Compare two prompts' agent trajectories side-by-side and return "
                        "shared / unique tool queries and whether the final answer matches."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt_a": {"type": "string", "description": "First prompt."},
                "prompt_b": {"type": "string", "description": "Second prompt."},
                "format": {"type": "string", "enum": ["json", "md"], "default": "md",
                           "description": "Diff output format."},
            },
            "required": ["prompt_a", "prompt_b"],
        },
    },
    {
        "name": "idun_packs",
        "description": "List the available bundled prompt packs (name, count, title).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "idun_run",
        "description": "Run a prompt from a bundled pack by name + key.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack": {"type": "string", "description": "Pack name, e.g. 'contoso'."},
                "key": {"type": "string", "description": "Prompt key inside the pack."},
            },
            "required": ["pack", "key"],
        },
    },
    {
        "name": "idun_token",
        "description": ("Inspect the stored Foundry token state WITHOUT exposing the secret. "
                        "Returns validity, seconds-until-expiry, and (if present) the account UPN. "
                        "Use this to debug auth before calling the agent tools."),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _client():
    return IdunClient()


def _tool_chat(prompt):
    res = _client().complete(prompt)
    return res.text


def _tool_trace(prompt):
    res = _client().complete(prompt)
    return {
        "text": res.text,
        "steps": [s.__dict__ for s in res.steps],
        "model": res.model,
    }


def _tool_export(prompt, fmt="json"):
    from idun import IdunResult
    res = _client().complete(prompt)
    if fmt == "md":
        return res.to_markdown()
    return res.to_json()


def _tool_diff(prompt_a, prompt_b, fmt="md"):
    from idun import diff_traces, format_diff
    ra = _client().complete(prompt_a)
    rb = _client().complete(prompt_b)
    d = diff_traces(ra, rb)
    return format_diff(d, fmt)


def _tool_packs():
    from idun import list_packs
    return list_packs()


def _tool_run(pack, key):
    from idun import get_prompt
    prompt = get_prompt(pack, key)
    return _tool_chat(prompt)


def _tool_token():
    """Inspect token state without leaking the secret."""
    import time
    info = {"has_env_token": bool(os.environ.get("FOUNDRY_TOKEN"))}
    try:
        from idun.auth import _load_meta
        meta = _load_meta()
        if meta:
            exp = float(meta.get("expires_at", 0))
            left = exp - time.time()
            info["stored_token_present"] = bool(meta.get("access_token"))
            info["expires_in_seconds"] = int(left)
            info["valid"] = left > 300
            acct = meta.get("account_upn") or meta.get("username")
            if acct:
                info["account"] = acct
        else:
            info["stored_token_present"] = False
            info["valid"] = False
    except Exception as e:
        info["error"] = str(e)[:200]
    return info


def _dispatch(req):
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "idun-mcp", "version": "0.1.23"},
            },
        }
    if method == "notifications/initialized":
        return None  # notification: no response
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "idun_chat":
                out = _tool_chat(args.get("prompt", ""))
                content = [{"type": "text", "text": str(out)}]
            elif name == "idun_trace":
                out = _tool_trace(args.get("prompt", ""))
                content = [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=2)}]
            elif name == "idun_export":
                out = _tool_export(args.get("prompt", ""), args.get("format", "json"))
                content = [{"type": "text", "text": str(out)}]
            elif name == "idun_diff":
                out = _tool_diff(args.get("prompt_a", ""), args.get("prompt_b", ""),
                                  args.get("format", "md"))
                content = [{"type": "text", "text": str(out)}]
            elif name == "idun_packs":
                out = _tool_packs()
                content = [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=2)}]
            elif name == "idun_run":
                out = _tool_run(args.get("pack", ""), args.get("key", ""))
                content = [{"type": "text", "text": str(out)}]
            elif name == "idun_token":
                out = _tool_token()
                content = [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=2)}]
            else:
                raise ValueError(f"unknown tool: {name}")
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": content}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32603, "message": str(e)[:400]}}
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main():
    # Provide a token if one is already stored and still valid. We do NOT call
    # load_token()/maybe_refresh() here: that would trigger an interactive
    # device-code login on an expired token, which hangs a headless MCP server.
    # A missing/invalid token simply yields a clean "no token" error on call.
    if not os.environ.get("FOUNDRY_TOKEN"):
        try:
            from idun.auth import _load_meta
            meta = _load_meta()
            if meta:
                exp = float(meta.get("expires_at", 0))
                tok = meta.get("access_token", "")
                # only use it if it is not already within the refresh slack
                if tok and (exp - __import__("time").time()) > 300:
                    os.environ["FOUNDRY_TOKEN"] = tok
        except Exception:
            pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _dispatch(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

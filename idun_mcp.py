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
]


def _tool_chat(prompt):
    cli = IdunClient()
    res = dict(cli.complete(prompt))
    return res.get("text", "")


def _tool_trace(prompt):
    cli = IdunClient()
    res = dict(cli.complete(prompt))
    return {
        "text": res.get("text", ""),
        "steps": res.get("steps", []),
        "model": res.get("model", ""),
    }


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
                "serverInfo": {"name": "idun-mcp", "version": "0.1.0"},
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

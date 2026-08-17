"""Tests for the MCP server parity (offline JSON-RPC-over-stdio contract)."""
import json

import idun_mcp as M
from idun.providers import Completion


def _dispatch(req):
    return M._dispatch(req)


def test_initialize_and_tools_list_includes_parity():
    init = _dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {}})
    assert init["result"]["serverInfo"]["name"] == "idun-mcp"
    names = {t["name"] for t in init and _dispatch(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})["result"]["tools"]}
    for expected in ("idun_chat", "idun_trace", "idun_providers",
                     "idun_ask", "idun_race"):
        assert expected in names


def test_idun_providers_tool(monkeypatch):
    # avoid live auth noise: stub the registry listing path is real, no network
    resp = _dispatch({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": "idun_providers", "arguments": {}}})
    assert "error" not in resp
    data = json.loads(resp["result"]["content"][0]["text"])
    ids = {p["id"] for p in data}
    assert "groq" in ids and "openai" in ids


def test_idun_ask_tool_routes_through_registry(monkeypatch, capsys):
    def fake(pid, prompt, **kw):
        return Completion(text="ans", model=kw.get("model") or "m",
                          provider=pid, prompt_tokens=1, completion_tokens=1,
                          latency_ms=5)
    monkeypatch.setattr(M.P, "complete", fake)
    resp = _dispatch({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                      "params": {"name": "idun_ask",
                                 "arguments": {"prompt": "hi",
                                               "provider": "groq"}}})
    assert "error" not in resp
    out = json.loads(resp["result"]["content"][0]["text"])
    assert out["provider"] == "groq"
    assert out["text"] == "ans"


def test_idun_race_tool_reports_state(monkeypatch):
    def fake(pid, prompt, **kw):
        return Completion(text="r", model="m", provider=pid,
                          prompt_tokens=1, completion_tokens=1, latency_ms=3)
    monkeypatch.setattr(M.P, "complete", fake)
    resp = _dispatch({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                      "params": {"name": "idun_race",
                                 "arguments": {"prompt": "hi",
                                               "providers": "groq,openai"}}})
    assert "error" not in resp
    out = json.loads(resp["result"]["content"][0]["text"])
    assert {r["provider"] for r in out} == {"groq", "openai"}
    assert all(r["state"] == "ok" for r in out)

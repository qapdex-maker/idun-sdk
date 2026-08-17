"""Offline tests for vision + function-calling wiring in idun.providers.

`_post_json` is monkeypatched so no network call is made; we assert the
request body the transport builds (image blocks + tool schemas) and that the
normalized Completion carries `tool_calls` back out. Pure stdlib.
"""
import json
import os

import idun.providers as P
from idun.providers import Completion, _extract_tool_calls


def _capture(p_transport, recorded):
    """Replace _post_json with a spy that records the request and returns a
    canned provider-shaped response for the matching transport."""
    import idun.providers as mod
    orig = mod._post_json

    def spy(url, body, headers, timeout):
        recorded["url"] = url
        recorded["body"] = body
        recorded["headers"] = headers
        # canned response shaped like the transport's success payload
        if p_transport == "openai":
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "The capital is Paris.",
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_weather",
                                         "arguments": '{"city": "Paris"}'},
                        }],
                    },
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        if p_transport == "anthropic":
            return {
                "content": [
                    {"type": "text", "text": "The capital is Paris."},
                    {"type": "tool_use", "id": "tu_1", "name": "get_weather",
                     "input": {"city": "Paris"}},
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        return {"generated_text": "The capital is Paris."}

    mod._post_json = spy
    return orig


def test_vision_openai_image_block():
    rec = {}
    orig = _capture("openai", rec)
    os.environ["GROQ_API_KEY"] = "test-key"
    try:
        P.complete("groq", "What is in this image?",
                   images=["https://example.com/cat.png"])
    finally:
        P._post_json = orig
    # the final user turn must be a list with a text + image_url block
    msgs = rec["body"]["messages"]
    last = msgs[-1]
    assert last["role"] == "user"
    assert isinstance(last["content"], list)
    types = [b.get("type") for b in last["content"]]
    assert "text" in types and "image_url" in types
    assert last["content"][1]["image_url"]["url"] == "https://example.com/cat.png"


def test_vision_anthropic_image_block():
    rec = {}
    orig = _capture("anthropic", rec)
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    try:
        P.complete("anthropic", "Describe this",
                   images=["https://example.com/cat.png"])
    finally:
        P._post_json = orig
    msgs = rec["body"]["messages"]
    last = msgs[-1]
    assert isinstance(last["content"], list)
    img_block = [b for b in last["content"] if b.get("type") == "image"][0]
    assert img_block["source"]["type"] == "url"
    assert img_block["source"]["url"] == "https://example.com/cat.png"


def test_tools_openai_roundtrip():
    rec = {}
    orig = _capture("openai", rec)
    os.environ["GROQ_API_KEY"] = "test-key"
    tools = [{"type": "function", "function": {
        "name": "get_weather", "description": "weather",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}]
    try:
        c = P.complete("groq", "Weather in Paris?", tools=tools,
                       tool_choice="auto")
    finally:
        P._post_json = orig
    # tool schema forwarded verbatim to openai body
    assert rec["body"]["tools"] == tools
    assert rec["body"]["tool_choice"] == "auto"
    # tool calls normalized onto the Completion
    assert isinstance(c, Completion)
    assert len(c.tool_calls) == 1
    assert c.tool_calls[0]["function"]["name"] == "get_weather"
    assert json.loads(c.tool_calls[0]["function"]["arguments"]) == {"city": "Paris"}
    assert c.text == "The capital is Paris."


def test_tools_anthropic_conversion():
    rec = {}
    orig = _capture("anthropic", rec)
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    tools = [{"type": "function", "function": {
        "name": "get_weather", "description": "weather",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}]
    try:
        c = P.complete("anthropic", "Weather in Paris?", tools=tools)
    finally:
        P._post_json = orig
    # anthropic tool schema uses input_schema, not parameters
    assert rec["body"]["tools"][0]["name"] == "get_weather"
    assert "input_schema" in rec["body"]["tools"][0]
    assert "parameters" not in rec["body"]["tools"][0]
    # tool_use block normalized to Completion.tool_calls (OpenAI shape)
    assert c.tool_calls[0]["function"]["name"] == "get_weather"
    assert json.loads(c.tool_calls[0]["function"]["arguments"]) == {"city": "Paris"}


def test_no_tools_no_tool_calls():
    rec = {}
    orig = _capture("openai", rec)
    os.environ["GROQ_API_KEY"] = "test-key"
    try:
        c = P.complete("groq", "hi")
    finally:
        P._post_json = orig
    # without explicit tools, the openai body must not carry a tools key
    assert "tools" not in rec["body"]
    assert "tool_choice" not in rec["body"]
    # (the spy's canned response happens to include tool_calls; that only proves
    #  _extract_tool_calls normalizes whatever the provider returns)
    assert isinstance(c, Completion)


def test_extract_tool_calls_handles_missing():
    assert _extract_tool_calls("openai", {"choices": [{"message": {"content": "x"}}]}) == []
    assert _extract_tool_calls("anthropic", {"content": [{"type": "text", "text": "x"}]}) == []
    assert _extract_tool_calls("hf", {"generated_text": "x"}) == []

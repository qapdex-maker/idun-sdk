"""pytest suite for idun-sdk (offline; no live Foundry call).

Covers:
- trajectory normalization (output array -> steps + text)
- request payload shape (model-router, no tools key)
- CLI entrypoint exposes login/chat/trace
- package importable as `idun`
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idun.client import IdunClient, _normalize_output


SAMPLE = {
    "model": "gpt-5.4-2026-03-05",
    "output": [
        {"type": "message", "role": "assistant",
         "content": [{"type": "output_text", "text": "Ich habe recherchiert: "}]},
        {"type": "reasoning", "text": "Ich pruefe, ob Contoso eine reale Marke ist."},
        {"type": "message", "role": "assistant",
         "content": [{"type": "output_text", "text": "Contoso setzt auf Kreislauf."}]},
        {"type": "web_search_call", "action": {"query": "Contoso Nachhaltigkeit"},
         "status": "completed", "id": "call_1"},
    ],
}


def test_normalize_trajectory():
    out = _normalize_output(SAMPLE)
    assert out.text.startswith("Ich habe recherchiert")
    assert "Contoso setzt auf Kreislauf" in out.text
    assert out.model == "gpt-5.4-2026-03-05"
    steps = out.steps
    kinds = [s.kind for s in steps]
    assert "reasoning" in kinds
    assert "tool" in kinds
    tool = next(s for s in steps if s.kind == "tool")
    assert tool.tool == "web_search"
    assert tool.query == "Contoso Nachhaltigkeit"
    assert tool.status == "completed"


def test_request_payload_shape():
    cli = IdunClient.__new__(IdunClient)
    payload = cli._build_payload("Hallo")
    assert payload["model"] == "model-router"
    assert payload["input"] == "Hallo"
    assert payload["max_output_tokens"] == 4096
    assert "tools" not in payload


def test_cli_entrypoint():
    from idun_cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["trace", "Was macht Contoso?"])
    assert args.command == "trace"
    assert args.prompt == "Was macht Contoso?"


def test_package_importable():
    import idun
    assert hasattr(idun, "__version__")

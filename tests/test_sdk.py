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


def test_trace_export_json():
    from idun import IdunResult, Step
    res = IdunResult(
        text="Final answer.",
        model="gpt-5.4-2026-03-05",
        steps=[
            Step(kind="reasoning", text="Plan: search."),
            Step(kind="tool", tool="web_search", query="Contoso CEO",
                  status="completed", id="s1"),
        ],
    )
    import json
    data = json.loads(res.to_json())
    assert data["text"] == "Final answer."
    assert data["model"] == "gpt-5.4-2026-03-05"
    assert len(data["steps"]) == 2
    assert data["steps"][1]["tool"] == "web_search"
    assert data["steps"][1]["query"] == "Contoso CEO"


def test_trace_export_markdown():
    from idun import IdunResult, Step
    res = IdunResult(
        text="Final answer.",
        model="gpt-5.4-2026-03-05",
        steps=[Step(kind="tool", tool="web_search", query="q", status="done")],
    )
    md = res.to_markdown()
    assert md.startswith("# Idun Trace")
    assert "**TOOL**" in md
    assert "## Final Answer" in md
    assert "Final answer." in md


def test_cli_export_subcommand():
    from idun_cli import build_parser
    args = build_parser().parse_args(
        ["export", "Was macht Contoso?", "--format", "md", "-o", "trace.md"])
    assert args.command == "export"
    assert args.fmt == "md"
    assert args.output == "trace.md"


def test_logo_path_resolves_bundled_svg():
    from idun import logo_path
    import os
    p = logo_path("white")
    assert p.endswith(".svg")
    assert os.path.exists(p), f"bundled logo missing: {p}"


def test_async_complete_offline(monkeypatch):
    import asyncio
    from idun import IdunClient, IdunResult
    c = IdunClient(token="fake")
    def fake_post(self, prompt, max_tokens):
        return {"model": "gpt-x", "output": [
            {"type": "message", "role": "assistant",
             "content": [{"type": "output_text", "text": "Hi"}]},
            {"type": "web_search_call", "action": {"query": "q"},
             "status": "completed", "id": "s1"}]}
    monkeypatch.setattr(IdunClient, "_post_once", fake_post)
    res = asyncio.run(c.complete_async("test", 4096))
    assert res.text == "Hi"
    assert len(res.steps) == 2
    assert res.steps[1].tool == "web_search"


def test_cli_async_flag_parses():
    from idun_cli import build_parser
    args = build_parser().parse_args(["chat", "Hi", "--async"])
    assert args.async_ is True
    args2 = build_parser().parse_args(["trace", "Hi", "--async"])
    assert args2.async_ is True
    args3 = build_parser().parse_args(["export", "Hi", "--async", "--format", "md"])
    assert args3.async_ is True
    from idun.auth import maybe_refresh
    # no token file -> returns None, no crash
    import os
    # ensure no leftover token file in HOME for this check
    bak = None
    tf = os.path.join(os.path.expanduser("~"), "foundry_token.txt")
    if os.path.exists(tf):
        bak = tf + ".bak"
        os.rename(tf, bak)
    try:
        assert maybe_refresh() is None
    finally:
        if bak and os.path.exists(bak):
            os.rename(bak, tf)


def test_contoso_pack_loading():
    from idun import list_packs, load_pack, get_prompt
    packs = list_packs()
    names = [p["name"] for p in packs]
    assert "contoso" in names
    contoso = next(p for p in packs if p["name"] == "contoso")
    assert contoso["count"] == 4
    data = load_pack("contoso")
    assert len(data["prompts"]) == 4
    text = get_prompt("contoso", "sustainability_summary")
    assert "Kreislauf" in text
    # error path
    try:
        get_prompt("contoso", "does_not_exist")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_cli_packs_and_run_subcommands():
    from idun_cli import build_parser
    # packs
    a1 = build_parser().parse_args(["packs"])
    assert a1.command == "packs"
    # run
    a2 = build_parser().parse_args(["run", "contoso", "esg_check", "--async"])
    assert a2.command == "run"
    assert a2.pack == "contoso"
    assert a2.key == "esg_check"
    assert a2.async_ is True


def test_trace_diff_offline():
    from idun import IdunResult, Step, diff_traces, format_diff
    a = IdunResult(text="Answer A", model="m", steps=[
        Step(kind="tool", tool="web_search", query="Contoso ESG", status="done"),
        Step(kind="tool", tool="web_search", query="Contoso News", status="done")])
    b = IdunResult(text="Answer B", model="m", steps=[
        Step(kind="tool", tool="web_search", query="Contoso ESG", status="done"),
        Step(kind="tool", tool="web_search", query="Contoso Finance", status="done")])
    d = diff_traces(a, b)
    assert d["shared_queries"] == ["Contoso ESG"]
    assert d["only_a"] == ["Contoso News"]
    assert d["only_b"] == ["Contoso Finance"]
    assert d["same_answer"] is False
    md = format_diff(d, "md")
    assert "# Idun Trace Diff" in md and "Shared tool queries" in md
    js = format_diff(d, "json")
    import json
    assert json.loads(js)["n_steps_a"] == 2


def test_cli_diff_subcommand():
    from idun_cli import build_parser
    a = build_parser().parse_args(["diff", "Prompt A", "Prompt B", "--format", "json"])
    assert a.command == "diff"
    assert a.prompt_a == "Prompt A"
    assert a.prompt_b == "Prompt B"
    assert a.fmt == "json"


def test_retry_backoff_on_transient_500(monkeypatch):
    """_post_with_retry retries 500/502/503/429 with backoff, succeeds on 2nd try."""
    from idun import IdunClient
    import urllib.error
    c = IdunClient(token="fake")
    calls = {"n": 0}

    def fake_post(self, prompt, max_tokens):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(c._url(), 500, "Server Error", {}, None)
        return {"model": "gpt-x", "output": [
            {"type": "message", "role": "assistant",
             "content": [{"type": "output_text", "text": "Recovered"}]}]}

    monkeypatch.setattr(IdunClient, "_post_once", fake_post)
    res = c.complete("test")
    assert calls["n"] == 2, "should have retried once"
    assert res.text == "Recovered"


def test_retry_gives_up_after_max_attempts(monkeypatch):
    """After max_attempts transient 5xx, raises RuntimeError with the code."""
    from idun import IdunClient
    import urllib.error
    c = IdunClient(token="fake")
    calls = {"n": 0}

    def fake_post(self, prompt, max_tokens):
        calls["n"] += 1
        raise urllib.error.HTTPError(c._url(), 503, "Unavailable", {}, None)

    monkeypatch.setattr(IdunClient, "_post_once", fake_post)
    try:
        c.complete("test", 4096)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "503" in str(e)
    assert calls["n"] == 3, "should attempt max_attempts=3 times"


def test_non_retryable_400_propagates_immediately(monkeypatch):
    """400 invalid_payload is NOT retried — fails on first attempt."""
    from idun import IdunClient
    import urllib.error
    c = IdunClient(token="fake")
    calls = {"n": 0}

    def fake_post(self, prompt, max_tokens):
        calls["n"] += 1
        raise urllib.error.HTTPError(c._url(), 400, "Bad Request", {}, None)

    monkeypatch.setattr(IdunClient, "_post_once", fake_post)
    try:
        c.complete("test")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "400" in str(e)
    assert calls["n"] == 1, "400 must not be retried"


def test_conversation_threads_history(monkeypatch):
    """Conversation.ask() prepends prior turns and records both sides."""
    from idun import IdunClient, Conversation
    c = IdunClient(token="fake")

    def fake_post(self, prompt, max_tokens):
        return {"model": "gpt-x", "output": [
            {"type": "message", "role": "assistant",
             "content": [{"type": "output_text", "text": "RESP:" + prompt[:40]}]}]}

    monkeypatch.setattr(IdunClient, "_post_once", fake_post)
    conv = Conversation(c)
    conv.ask("First question?")
    assert len(conv.history) == 2  # user + assistant
    conv.ask("Second question?")
    assert len(conv.history) == 4
    rendered = conv._render("probe")
    assert "Previous conversation:" in rendered
    assert "[user] First question?" in rendered
    assert "[user] Second question?" in rendered
    conv.clear()
    assert conv.history == []

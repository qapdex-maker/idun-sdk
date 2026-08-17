"""Offline tests for `idun chat` interactive (no-prompt) session mood."""
import idun_cli as C


def test_chat_intro_prints_online(monkeypatch, capsys):
    # chat_intro must render an "IDUN ONLINE" live header, not the help text
    def fake_input(prompt=""):
        return "exit"

    monkeypatch.setattr("builtins.input", fake_input)
    args = C.build_parser().parse_args(["chat"])
    C.cmd_chat(args)
    err = capsys.readouterr().err
    assert "IDUN ONLINE" in err
    assert "interactive session" in err
    assert "console live" in err


def test_chat_repl_runs_prompt_then_exits(monkeypatch, capsys):
    calls = []

    class _Res:
        text = "answer"
        model = "m"

    def fake_input(prompt=""):
        if calls:
            return "exit"
        calls.append(1)
        return "hello there"

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(C, "_run", lambda args, prompt: _Res())
    args = C.build_parser().parse_args(["chat"])
    C.cmd_chat(args)
    err = capsys.readouterr().err
    assert "IDUN ONLINE" in err
    assert "session closed." in err
    assert calls == [1]  # exactly one real input before exit


def test_chat_with_prompt_still_one_shot(monkeypatch, capsys):
    class _Res:
        text = "single"
        model = "m"

    monkeypatch.setattr(C, "_run", lambda args, prompt: _Res())
    args = C.build_parser().parse_args(["chat", "just one"])
    C.cmd_chat(args)
    err = capsys.readouterr().err
    # no REPL header when a prompt is supplied on the command line
    assert "IDUN ONLINE" not in err
    assert "IDUN RESPONSE" in err
    assert "single" in err

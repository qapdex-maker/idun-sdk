"""Offline tests for idun.hf_pipeline + the `idun hf` CLI subcommand."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idun import hf_pipeline as hf
import idun_cli


def test_load_hf_token_env(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_env_xxx")
    monkeypatch.setattr(hf, "open", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError),
                        raising=False)
    assert hf.load_hf_token() == "hf_env_xxx"


def test_load_hf_token_hub_env(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HUGGING_FACE_HUB_TOKEN", "hf_hub_xxx")
    assert hf.load_hf_token() == "hf_hub_xxx"


def test_hf_infer_shape(monkeypatch):
    def fake(*a, **k):
        # emulate urllib response context manager
        class R:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return b'[{"generated_text": "hello world"}]'
        return R()
    monkeypatch.setattr(hf.urllib.request, "urlopen", lambda *a, **k: fake())
    out = hf.hf_infer("hi", token="t", model="m")
    assert out == "hello world"


def test_hf_whoami_error(monkeypatch):
    import urllib.error
    class E(urllib.error.HTTPError):
        def __init__(self, code):
            self.code = code
        def read(self):
            return b"bad token"
    monkeypatch.setattr(hf.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(E(401)))
    try:
        hf.hf_whoami("x")
        assert False, "should raise"
    except RuntimeError as e:
        assert "401" in str(e)


def test_hf_model_status_404(monkeypatch):
    import urllib.error
    class E(urllib.error.HTTPError):
        def __init__(self, code):
            self.code = code
        def read(self):
            return b"not found"
    monkeypatch.setattr(hf.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(E(404)))
    st = hf.hf_model_status("nope/model")
    assert st["exists"] is False
    assert st["error"] is None


def test_hf_model_status_ok(monkeypatch):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return b'{"gated": null, "private": false, "pipeline_tag": "text-generation"}'
    monkeypatch.setattr(hf.urllib.request, "urlopen", lambda *a, **k: R())
    st = hf.hf_model_status("microsoft/phi-3-mini-4k-instruct")
    assert st["exists"] is True
    assert st["pipeline_tag"] == "text-generation"


def test_cli_hf_parser_present():
    p = idun_cli.build_parser()
    # hf subcommand with nested whoami/status/push
    ns = p.parse_args(["hf", "whoami"])
    assert ns.command == "hf"
    assert ns.hf_command == "whoami"
    ns2 = p.parse_args(["hf", "status", "microsoft/phi-3-mini-4k-instruct"])
    assert ns2.model == "microsoft/phi-3-mini-4k-instruct"
    ns3 = p.parse_args(["hf", "push", "qapdex/x", "a.txt", "b.txt", "--private"])
    assert ns3.model == "qapdex/x"
    assert ns3.files == ["a.txt", "b.txt"]
    assert ns3.private is True


def test_cli_hf_whoami_missing_token(monkeypatch, capsys):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.setattr(hf, "open", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError),
                        raising=False)
    args = idun_cli.build_parser().parse_args(["hf", "whoami"])
    rc = idun_cli.cmd_hf(args)
    assert rc == 1
    assert "missing" in capsys.readouterr().err.lower()

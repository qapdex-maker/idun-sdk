"""Offline tests for the multi-provider registry and the retro renderer.

No network: transports are monkeypatched. Run with `pytest tests/`.
"""
from __future__ import annotations

import os

import pytest

from idun import providers as P
from idun import retro as R


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def test_registry_ids_unique_and_nonempty():
    ids = [p.id for p in P.list_providers()]
    assert len(ids) == len(set(ids)), "duplicate provider id"
    assert len(ids) >= 10


def test_every_provider_has_base_and_model():
    for p in P.list_providers():
        assert p.base.startswith("http"), p.id
        assert p.default_model, p.id
        assert p.transport in ("openai", "anthropic", "hf", "azure", "cloudflare"), p.id


def test_get_provider_is_case_insensitive():
    assert P.get_provider("OpenAI").id == "openai"
    assert P.get_provider("  OPENROUTER  ").id == "openrouter"


def test_get_provider_has_no_aliases():
    """'github' used to map onto openai, mixing credentials. It must not.

    See tests/test_no_provider_aliasing.py for the full rationale.
    """
    with pytest.raises(ValueError):
        P.get_provider("github")


def test_get_provider_rejects_unknown():
    with pytest.raises(ValueError):
        P.get_provider("does-not-exist")


def test_env_overrides_model_and_base(monkeypatch):
    p = P.get_provider("groq")
    monkeypatch.setenv(p.model_env(), "custom-model")
    monkeypatch.setenv(p.base_env(), "https://example.invalid/v1")
    assert p.resolved_model() == "custom-model"
    assert p.resolved_base() == "https://example.invalid/v1"


def test_credential_from_env_preferred(monkeypatch):
    p = P.get_provider("groq")
    monkeypatch.setenv("GROQ_API_KEY", "secret-key")
    assert P.resolve_credential(p) == "secret-key"
    assert P.credential_status(p) == "env:GROQ_API_KEY"


def test_credential_roundtrip_via_file(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(P, "CONFIG_DIR", str(tmp_path))
    p = P.replace(P.get_provider("groq"), id="groq")
    # token_file derives from CONFIG_DIR at call time
    monkeypatch.setattr(type(p), "token_file",
                        property(lambda self: str(tmp_path / f"{self.id}.token")))
    path = P.save_credential(p, "  file-key  ")
    assert P.resolve_credential(p) == "file-key"
    assert oct(os.stat(path).st_mode)[-3:] == "600"


def test_missing_credential_raises(monkeypatch):
    for key in ("GROQ_API_KEY",):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(P, "CONFIG_DIR", "/nonexistent-idun-dir")
    monkeypatch.setattr(type(P.get_provider("groq")), "token_file",
                        property(lambda self: "/nonexistent-idun-dir/x.token"))
    with pytest.raises(RuntimeError, match="no credential"):
        P.complete("groq", "hi")


def test_default_provider_env_precedence(monkeypatch):
    monkeypatch.delenv("IDUN_PROVIDER", raising=False)
    monkeypatch.delenv("IDUN_BACKEND", raising=False)
    assert P.default_provider() == "azure"
    monkeypatch.setenv("IDUN_BACKEND", "hf")
    assert P.default_provider() == "hf"
    monkeypatch.setenv("IDUN_PROVIDER", "groq")
    assert P.default_provider() == "groq"


# --------------------------------------------------------------------------
# response normalization
# --------------------------------------------------------------------------


def test_extract_text_openai_shape():
    data = {"choices": [{"message": {"content": "hello"}}]}
    assert P._extract_text("openai", data) == "hello"


def test_extract_text_anthropic_shape():
    data = {"content": [{"type": "text", "text": "claude "},
                        {"type": "text", "text": "here"}]}
    assert P._extract_text("anthropic", data) == "claude here"


def test_extract_text_hf_shapes():
    assert P._extract_text("hf", [{"generated_text": "gen"}]) == "gen"
    assert P._extract_text(
        "hf", [{"generated_text": {"content": "chat"}}]) == "chat"


def test_extract_usage_variants():
    assert P._extract_usage(
        "openai", {"usage": {"prompt_tokens": 3, "completion_tokens": 4}}) == (3, 4)
    assert P._extract_usage(
        "anthropic", {"usage": {"input_tokens": 5, "output_tokens": 6}}) == (5, 6)
    assert P._extract_usage("openai", {}) == (0, 0)


def test_complete_returns_normalized_completion(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")

    def fake_post(url, body, headers, timeout):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer k"
        assert body["model"] == "test-model"
        return {"choices": [{"message": {"content": " hi there "}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3}}

    monkeypatch.setattr(P, "_post_json", fake_post)
    c = P.complete("groq", "prompt", model="test-model")
    assert c.text == "hi there"
    assert (c.provider, c.model) == ("groq", "test-model")
    assert c.total_tokens == 5
    assert c.latency_ms >= 0


def test_complete_passes_system_prompt(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    seen = {}

    def fake_post(url, body, headers, timeout):
        seen.update(body)
        return {"choices": [{"message": {"content": "x"}}]}

    monkeypatch.setattr(P, "_post_json", fake_post)
    P.complete("groq", "u", system="be terse")
    assert seen["messages"][0] == {"role": "system", "content": "be terse"}
    assert seen["messages"][1]["role"] == "user"


def test_anthropic_uses_x_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak")
    seen = {}

    def fake_post(url, body, headers, timeout):
        seen["url"] = url
        seen["headers"] = headers
        return {"content": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(P, "_post_json", fake_post)
    c = P.complete("anthropic", "hi")
    assert seen["url"].endswith("/messages")
    assert seen["headers"]["x-api-key"] == "ak"
    assert "anthropic-version" in seen["headers"]
    assert c.text == "ok"


def test_http_error_is_wrapped(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")

    def boom(url, body, headers, timeout):
        raise RuntimeError("HTTP 429 from x: rate limited")

    monkeypatch.setattr(P, "_post_json", boom)
    with pytest.raises(RuntimeError, match="429"):
        P.complete("groq", "hi")


# --------------------------------------------------------------------------
# retro renderer
# --------------------------------------------------------------------------


def test_strip_len_ignores_ansi():
    assert R.strip_len("\033[31mred\033[0m") == 3
    assert R.strip_len("plain") == 5


def test_paint_noop_without_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert R.paint("x", "ok") == "x"


def test_paint_wraps_with_forced_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("IDUN_NO_RETRO", raising=False)
    monkeypatch.setenv("IDUN_FORCE_COLOR", "1")
    out = R.paint("x", "ok")
    assert out.startswith("\033[") and out.endswith("\033[0m")


def test_box_lines_are_equal_width(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    rendered = R.box(["short", "a much longer line here"], title="T")
    lines = rendered.split("\n")
    widths = {R.strip_len(ln) for ln in lines}
    assert len(widths) == 1, f"ragged box: {widths}"


def test_box_handles_embedded_newlines(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    rendered = R.box(["one\ntwo\nthree"], title="X")
    assert len({R.strip_len(ln) for ln in rendered.split("\n")}) == 1
    assert "two" in rendered


def test_box_survives_colored_content(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("IDUN_FORCE_COLOR", "1")
    rendered = R.box([R.status("ok", "fine"), R.status("err", "bad")], title="S")
    assert len({R.strip_len(ln) for ln in rendered.split("\n")}) == 1


def test_table_aligns_colored_cells(monkeypatch):
    monkeypatch.setenv("IDUN_FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    rows = [("a", R.paint("ok", "ok")), ("bbbb", R.paint("FAILED", "err"))]
    out = R.table(rows, headers=("name", "state"))
    # header + underline + 2 rows
    assert len(out.split("\n")) == 4


def test_bar_bounds(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert "100%" in R.bar(1.5)
    assert "  0%" in R.bar(-3)


def test_logo_contains_tagline():
    assert "MULTI-PROVIDER" in R.logo("9.9.9")
    assert "9.9.9" in R.logo("9.9.9")


def test_ascii_mode_avoids_unicode(monkeypatch):
    monkeypatch.setenv("IDUN_ASCII", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    rendered = R.box(["x"], title="T")
    assert "╔" not in rendered and "+" in rendered
    rendered.encode("ascii")  # must not raise


# --------------------------------------------------------------------------
# console-script hijack guard (regression test for audit failure F1)
# --------------------------------------------------------------------------


def test_shim_check_detects_hijack(tmp_path, monkeypatch):
    import shutil
    import idun_multi as M

    fake = tmp_path / "idun"
    fake.write_text("#!/usr/bin/env python3\nfrom llamacpp_vulkan import main\n")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(shutil, "which",
                        lambda n: str(fake) if n == "idun" else None)
    out = M._shim_check()
    joined = "\n".join(out)
    assert "HIJACKED" in joined
    assert "llamacpp_vulkan" in joined


def test_shim_check_accepts_correct_shim(tmp_path, monkeypatch):
    import shutil
    import idun_multi as M

    good = tmp_path / "idun"
    good.write_text("#!/usr/bin/env python3\nfrom idun_cli import main\n")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(shutil, "which",
                        lambda n: str(good) if n == "idun" else None)
    joined = "\n".join(M._shim_check())
    assert "HIJACKED" not in joined
    assert "idun_cli" in joined

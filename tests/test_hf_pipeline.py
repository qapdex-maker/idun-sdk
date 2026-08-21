"""`idun hf` must use a host that still resolves (BUG 7).

Why this file exists
--------------------
`idun/hf_pipeline.py` pointed its inference call at
``api-inference.huggingface.co`` — the same dead host as the old `hf` provider
(BUG 5). DNS no longer resolves it, so every `idun hf ...` inference call dies
before reaching the network. The Hub calls (`whoami`, `model_status`, `upload`)
use `huggingface.co`, which is still alive, so only the inference path was
broken.

Two more inconsistencies surfaced while fixing this:

* Token source mismatch: `load_hf_token()` read `HF_TOKEN` env or
  `~/hf_token.txt`, but NOT `~/.idun/hf.token` — the file `idun-multi login`
  and `resolve_credential` actually populate. So `idun hf` would never see the
  token a user stored via the wizard/login flow.
* ``SUGGESTED_TEXT_MODELS`` listed `microsoft/phi-3-mini-4k-instruct`, which no
  longer exists on the router (verified: model_not_found).

Decision: route inference through the same OpenAI-compatible router the provider
uses (`https://router.huggingface.co/v1`), so one working endpoint serves both.
These tests are offline (no network) — they assert the URLs and token source,
not a live call.
"""
from __future__ import annotations

from idun import hf_pipeline as hf


def test_inference_uses_live_router_not_dead_host():
    """hf_infer must target router.huggingface.co, never api-inference."""
    assert hf.HF_INFERENCE == "https://router.huggingface.co/v1"
    assert "api-inference.huggingface.co" not in hf.HF_INFERENCE


def test_inference_url_is_openai_compatible_v1():
    url = f"{hf.HF_INFERENCE}/chat/completions"
    assert url == "https://router.huggingface.co/v1/chat/completions"


def test_hub_endpoints_still_alive():
    """Hub calls (whoami/status) use huggingface.co, which is still up."""
    assert hf.HF_API == "https://huggingface.co"


def test_load_hf_token_reads_idun_token_file(monkeypatch, tmp_path):
    """Token must come from ~/.idun/hf.token — the file login/wizard write.

    Before the fix load_hf_token only read HF_TOKEN env or ~/hf_token.txt,
    so `idun hf` never saw the token stored via `idun-multi login --backend hf`.
    """
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    # no ~/hf_token.txt in our fake home
    # but ~/.idun/hf.token exists
    idun_dir = tmp_path / ".idun"
    idun_dir.mkdir()
    (idun_dir / "hf.token").write_text("TOKEN-FROM-IDUN-FILE", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    got = hf.load_hf_token()
    assert got == "TOKEN-FROM-IDUN-FILE", (
        f"load_hf_token did not read ~/.idun/hf.token, got {got!r}"
    )


def test_suggested_models_exist_on_router():
    """Default trial models must exist on the router (no model_not_found)."""
    for m in hf.SUGGESTED_TEXT_MODELS:
        assert m != "microsoft/phi-3-mini-4k-instruct", (
            "phi-3-mini-4k-instruct was retired from the router; remove it"
        )
        assert "/" in m, f"suggested model {m!r} should be a repo id (org/name)"

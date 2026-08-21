"""The HuggingFace provider must point at an endpoint that still exists.

Why this file exists
--------------------
The registry pointed ``hf`` at ``https://api-inference.huggingface.co/models``.
That host was retired by HuggingFace and no longer resolves at all:

    [FAIL] cannot reach https://api-inference.huggingface.co/models/...:
           [Errno 7] No address associated with hostname

Verified it was not a local network problem -- openrouter.ai, huggingface.co and
router.huggingface.co all resolved fine in the same DNS check while
api-inference.huggingface.co did not.

Worse, ``hf`` was declared ``needs_key=False``, so ``idun-multi doctor`` listed
it under READY. A provider that reports itself ready and then dies on a DNS
error is the most misleading state possible.

The replacement ``https://router.huggingface.co/v1`` is OpenAI-compatible
(``GET /v1/models`` -> HTTP 200) and requires authentication: an anonymous
chat/completions call returns HTTP 401. So the migration has two parts -- the
base URL *and* the credential requirement.

These are offline registry assertions; no network access is needed to run them.
"""
from __future__ import annotations

import pytest

from idun import providers as P


@pytest.fixture
def hf():
    return P.get_provider("hf")


def test_hf_does_not_use_the_retired_host(hf):
    """The dead api-inference host must not appear anywhere in the provider."""
    assert "api-inference.huggingface.co" not in hf.base, (
        "hf still points at api-inference.huggingface.co, which no longer "
        "resolves (DNS: no address associated with hostname)"
    )


def test_hf_uses_the_router_endpoint(hf):
    """hf must target the current HuggingFace router endpoint."""
    assert "router.huggingface.co" in hf.base, (
        f"expected the router endpoint, got {hf.base!r}"
    )


def test_hf_base_is_openai_compatible_v1(hf):
    """The router endpoint speaks the OpenAI dialect under /v1."""
    assert hf.base.rstrip("/").endswith("/v1"), (
        f"router.huggingface.co exposes an OpenAI-compatible API at /v1; "
        f"base is {hf.base!r}"
    )


def test_hf_requires_a_key(hf):
    """Anonymous access is gone: the router returns HTTP 401 without a token.

    Declaring needs_key=False made `doctor` list hf as READY while it was
    unusable. The credential requirement is part of the migration.
    """
    assert hf.needs_key is True, (
        "hf must declare needs_key=True: an anonymous call to "
        "router.huggingface.co/v1/chat/completions returns HTTP 401"
    )


def test_hf_env_keys_are_preserved(hf):
    """Existing HF_TOKEN / HUGGING_FACE_HUB_TOKEN setups must keep working."""
    assert "HF_TOKEN" in hf.env_keys
    assert "HUGGING_FACE_HUB_TOKEN" in hf.env_keys


def test_no_provider_uses_a_dead_hf_host():
    """Generic guard: the retired host must not reappear in any provider."""
    offenders = [p.id for p in P.REGISTRY if "api-inference.huggingface.co" in p.base]
    assert not offenders, f"providers still using the retired HF host: {offenders}"

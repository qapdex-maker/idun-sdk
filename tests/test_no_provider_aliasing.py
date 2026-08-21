"""``github`` must not silently resolve to a different provider's credentials.

Why this file exists
--------------------
``get_provider()`` carried a "legacy alias" that rewrote ``github`` to
``openai``:

    if key == "github":
        key = "openai"

Two consequences, both bad:

1. ``github`` is not in REGISTRY, so it never appears in the provider picker --
   the user cannot select it -- yet ``get_provider("github")`` happily returns a
   provider. The CLI and the registry disagreed about what exists.

2. The returned provider carries ``token_file`` = ``~/.idun/openai.token``. A
   GitHub credential entered under the name ``github`` would be written into
   OpenAI's secret store and then sent to ``api.openai.com``. GitHub Models is a
   separate service (its own endpoint, a GitHub PAT as credential), so the key
   would be transmitted to the wrong host and OpenAI's own key would be
   overwritten.

Decision (owner, 21.08.2026): remove the alias and fail with a clear message.
No half-support for a service that cannot be tested. If GitHub Models is added
later it becomes a real provider with its own endpoint and its own token file,
not an alias.
"""
from __future__ import annotations

import pytest

from idun import providers


def test_github_is_not_a_silent_alias():
    """``get_provider("github")`` must not return some other provider."""
    with pytest.raises(ValueError):
        providers.get_provider("github")


def test_github_error_message_is_actionable():
    """The failure must name the problem and point somewhere useful.

    A bare "unknown provider" would leave a user who followed older docs
    guessing. The message should mention github explicitly.
    """
    with pytest.raises(ValueError) as exc:
        providers.get_provider("github")
    msg = str(exc.value)
    assert "github" in msg.lower(), f"message does not mention github: {msg!r}"
    # Must not silently suggest that it worked; must list what does exist.
    assert "openai" in msg.lower(), (
        "message should point the user at the providers that do exist"
    )


def test_github_never_maps_to_openai_token_file():
    """No lookup may hand out OpenAI's secret store under the name github.

    This is the credential-mixing guard: it must be impossible to write a
    GitHub PAT into ~/.idun/openai.token via the github name.
    """
    try:
        p = providers.get_provider("github")
    except ValueError:
        return  # correct behaviour: no provider, no token file
    pytest.fail(
        f"get_provider('github') returned provider {p.id!r} with token_file "
        f"{p.token_file!r} -- a github credential would land in another "
        f"provider's secret store"
    )


def test_registry_and_lookup_agree():
    """Every id resolvable via get_provider must be listed in REGISTRY.

    The alias broke this invariant: 'github' resolved but was not listed. Any
    future alias would reintroduce the same inconsistency, so the contract is
    tested generically rather than only for 'github'.
    """
    listed = {p.id for p in providers.REGISTRY}
    for pid in listed:
        assert providers.get_provider(pid).id == pid, (
            f"get_provider({pid!r}) did not return the provider with that id"
        )
    # And a name that is not listed must not resolve.
    for unknown in ("github", "copilot", "definitely-not-a-provider"):
        if unknown in listed:
            continue
        with pytest.raises(ValueError):
            providers.get_provider(unknown)


def test_known_providers_still_resolve():
    """The removal must not break the providers that legitimately exist."""
    for pid in ("openai", "openrouter", "anthropic", "groq", "nous"):
        assert providers.get_provider(pid).id == pid

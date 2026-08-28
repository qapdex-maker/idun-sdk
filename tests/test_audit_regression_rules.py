"""O8 — Audit-Regeln (ROADMAP-FIX A1-A5) als erzwingbare Tests.

Hintergrund
-----------
Die grünen Tests von vor B1-B10 hatten drei strukturelle Blindstellen, die
echte Bugs durchließen (siehe ROADMAP-FIX.md Teil A):

  A1  Mocks ersetzen genau die Funktion, die geprüft wird. Ein Test, der
      ``save_credential`` wegmockt und nur prüft "wird sie aufgerufen", beweist
      nichts über das Speichern.
  A2  Frisches tmp_path macht Zustandsfehler unerreichbar (O_EXCL kann nur
      scheitern, wenn die Datei schon da ist). -> "zweimal aufrufen" nötig.
  A3  Verpackung (console_scripts) wird gar nicht getestet.
  A4  Tests prüfen Verdrahtung ("wird X aufgerufen?") statt Verhalten
      ("tut X das Richtige?").
  A5  Gesamt-Audit der Suite: was wird gemockt, was wirklich geprüft.

A2 ist bereits durch ``test_credential_overwrite.py`` abgedeckt (9 Tests,
echte Persistenz, kein Mock von save_credential, vorbelegter Zustand).
A3 ist durch ``test_packaging_contract.py`` abgedeckt.

Diese Datei schließt die verbleibende Lücke O8 / A1 / A4:

  1. Ein Test, der die Persistenz-Funktion NICHT mockt und echtes Verhalten
     prüft (Datei entsteht wirklich, Inhalt exakt = Token, resolve liefert
     exakt den Wert — nicht nur "irgendwas wurde gespeichert").
  2. Ein Guard, der sicherstellt, dass ``save_credential`` in KEINEM Test per
     monkeypatch ersetzt wird (sonst würde A1 still zurückkehren).
  3. Ein Verhaltens-Test: resolve_credential muss den exakten Token-String
     zurückgeben, nicht nur einen Truthy-Wert.

Diese Regeln sind bewusst generisch — sie sollen künftige Regressionen der
Klasse "grüne Tests, aber kaputt am echten Gerät" verhindern.
"""
from __future__ import annotations

import os

import pytest

from idun import providers


@pytest.fixture
def isolated_config(monkeypatch, tmp_path):
    """Point CONFIG_DIR at a temp dir. Never touches the real ~/.idun."""
    monkeypatch.setattr(providers, "CONFIG_DIR", str(tmp_path))
    return tmp_path


# --------------------------------------------------------------------------
# A1 / A4: behaviour, not wiring — no mock of the persistence function
# --------------------------------------------------------------------------


def test_save_persists_real_file_with_exact_content(isolated_config):
    """save_credential must write a real file whose content IS the token.

    This is the A1/A4 guard: we do NOT patch save_credential. We assert the
    actual on-disk effect, not merely "the function was called". A test that
    monkeypatches save_credential away and checks call count would pass even
    if saving were completely broken.
    """
    p = providers.get_provider("openai")
    path = providers.save_credential(p, "sk-exact-value")
    # File really exists on disk (not just "a call happened").
    assert os.path.isfile(path), "save_credential did not create a file"
    # Content is EXACTLY the token (behaviour, not wiring).
    with open(path, "r", encoding="utf-8") as fh:
        assert fh.read() == "sk-exact-value"
    # resolve returns the exact same value.
    assert providers.resolve_credential(p) == "sk-exact-value"


def test_resolve_returns_exact_token_not_truthy(isolated_config):
    """resolve_credential must round-trip the precise token string.

    A4 guard: asserting ``resolve_credential(p)`` is truthy would also pass if
    the implementation returned a constant placeholder. We require equality
    with the stored value.
    """
    p = providers.get_provider("groq")
    providers.save_credential(p, "groq-precise-123")
    assert providers.resolve_credential(p) == "groq-precise-123"
    # A different provider must not cross-contaminate.
    q = providers.get_provider("openai")
    providers.save_credential(q, "openai-precise-456")
    assert providers.resolve_credential(p) == "groq-precise-123"
    assert providers.resolve_credential(q) == "openai-precise-456"


# --------------------------------------------------------------------------
# A1 guard: save_credential must never be mocked away in the suite
# --------------------------------------------------------------------------


def test_save_credential_is_not_monkeypatched_anywhere():
    """Static guard: no test file may replace save_credential with a fake.

    If a future test reintroduces the A1 anti-pattern (monkeypatch /
    unittest.mock replacing the persistence *write* function under test),
    this fails loudly at collection time — before any green-but-broken run
    can ship.

    NOTE: ``resolve_credential`` (the read side) IS legitimately mocked at the
    auth boundary in transport/cache tests (e.g. test_cache_retry.py uses a
    fake token to exercise the cache without a real credential). That matches
    ROADMAP-FIX A1 ("mocks only at the system boundary — never at the boundary
    being tested"): those tests check transport/cache, not token loading, so
    mocking the auth boundary is correct. Only the *write* path (save_credential)
    is forbidden to be mocked, because that was the exact function the wizard
    tests replaced with a no-op — hiding B2.
    """
    tests_dir = os.path.dirname(__file__)
    patched = []
    for name in os.listdir(tests_dir):
        if not name.startswith("test_") or not name.endswith(".py"):
            continue
        if name == os.path.basename(__file__):
            continue
        path = os.path.join(tests_dir, name)
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        # Matches: monkeypatch.setattr(providers, "save_credential", ...)
        #          monkeypatch.setattr("idun.providers.save_credential", ...)
        #          patch("idun.providers.save_credential", ...) etc.
        if 'save_credential' in src and (
            "setattr" in src or "mock.patch" in src or "patch(" in src
        ):
            # Only flag if the patch TARGETS save_credential specifically.
            if '"save_credential"' in src or "'save_credential'" in src or \
               "save_credential," in src or "save_credential)" in src:
                patched.append(name)
    assert patched == [], (
        "save_credential is mocked away in these test files (A1 anti-pattern "
        "would return): " + ", ".join(patched)
    )

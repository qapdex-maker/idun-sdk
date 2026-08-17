"""Offline tests for the support-matrix helpers (idun.providers).

The matrix must be derived from the registry, not hard-coded, and must agree
with the JSON-mode rule already used by `cmd_schema` (openai + azure only).
"""
import idun.providers as P
from idun.providers import support_matrix, get_provider


def test_matrix_covers_every_provider():
    rows = support_matrix()
    ids = [r["id"] for r in rows]
    registry_ids = [p.id for p in P.list_providers()]
    assert ids == registry_ids, "matrix must list exactly the registry providers"


def test_matrix_json_mode_matches_schema_rule():
    """`json_mode` in the matrix must equal the openai/azure transport rule
    used by cmd_schema (`p.transport in ('openai', 'azure')`)."""
    for r in support_matrix():
        p = get_provider(r["id"])
        expected = p.transport in ("openai", "azure")
        assert r["json_mode"] is expected, \
            f"{r['id']}: json_mode {r['json_mode']} != transport rule {expected}"


def test_matrix_known_shapes():
    rows = {r["id"]: r for r in support_matrix()}
    # azure: tool-agent -> streaming + tools + json
    assert rows["azure"]["streaming"] is True
    assert rows["azure"]["tools"] is True
    assert rows["azure"]["json_mode"] is True
    # openai transport: streaming + json, no tools / vision
    assert rows["groq"]["streaming"] is True
    assert rows["groq"]["json_mode"] is True
    assert rows["groq"]["tools"] is False
    # anthropic / hf: nothing special
    assert rows["anthropic"]["streaming"] is False
    assert rows["anthropic"]["json_mode"] is False
    assert rows["hf"]["streaming"] is False
    assert rows["hf"]["json_mode"] is False


def test_matrix_text_is_markdown_table():
    txt = P.support_matrix_text()
    assert txt.startswith("| Provider")
    assert "|---" in txt
    # every provider id appears as a backticked cell
    for p in P.list_providers():
        assert f"`{p.id}`" in txt

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
    # azure: tool-agent -> streaming + json; complete() itself is text-only
    # (the agent tool-trace is surfaced via IdunClient, not complete()).
    assert rows["azure"]["streaming"] is True
    assert rows["azure"]["tools"] is False
    assert rows["azure"]["json_mode"] is True
    # openai transport: streaming + json + tools + vision (wired through complete())
    assert rows["groq"]["streaming"] is True
    assert rows["groq"]["json_mode"] is True
    assert rows["groq"]["tools"] is True
    assert rows["groq"]["vision"] is True
    # anthropic: tools + vision, no streaming / json_mode
    assert rows["anthropic"]["streaming"] is False
    assert rows["anthropic"]["tools"] is True
    assert rows["anthropic"]["vision"] is True
    assert rows["anthropic"]["json_mode"] is False
    # hf now rides the openai-compatible router, so it exposes the same
    # capabilities as the other openai-transport providers. Assert the rule
    # instead of a hard-coded "nothing" -- the old assertion froze hf into the
    # pre-migration state (needs_key=False, transport="hf").
    assert rows["hf"]["streaming"] is True
    assert rows["hf"]["json_mode"] is True
    assert rows["hf"]["tools"] is True
    assert rows["anthropic"]["json_mode"] is False


def test_matrix_text_is_markdown_table():
    txt = P.support_matrix_text()
    assert txt.startswith("| Provider")
    assert "|---" in txt
    # every provider id appears as a backticked cell
    for p in P.list_providers():
        assert f"`{p.id}`" in txt

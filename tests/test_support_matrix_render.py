"""Regression tests for the rendered support-matrix document.

Written 2026-11-16 as the required red test BEFORE any fix. The matrix renderer
currently embeds a literal ``\\n`` in its header and the checked-in document is
stale; both must be caught by tests, not by reading a green suite.
"""
from idun import verification as V
from idun.providers import support_matrix_text


def test_rendered_matrix_uses_real_newlines():
    text = support_matrix_text()
    assert "\\n" not in text, "header contains a literal backslash-n instead of a line break"
    lines = text.splitlines()
    assert lines[0].startswith("| Provider |"), lines[0]
    assert lines[1].startswith("|---"), lines[1]


def test_rendered_matrix_reflects_verification_log(monkeypatch):
    monkeypatch.setattr(V, "state", lambda _pid: V.VerifyRecord(state=V.OK))
    assert "✓ live" in support_matrix_text()

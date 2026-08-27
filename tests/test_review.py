"""Tests for the self-built reviewer's structured-output layer (Solide-Stufe).

These run fully offline: they never call an LLM or GitHub. They cover the
review-text parser, severity->label mapping, and the chunk cache round-trip.
"""

import json
import os

import idun.review_parse as RP
from idun import review_cache as RC


def _sample_review_text(provider: str) -> str:
    return (
        f"[{provider}] [HIGH] src/auth.py:42 token leaked via log\n"
        f"[{provider}] [MEDIUM] src/db.py:10 missing input validation\n"
        f"[{provider}] KEINE FUNDE"
    )


def test_parse_finding_with_severity_and_location():
    fs = RP.parse_findings("[HIGH] src/foo.py:42 use of eval is unsafe")
    assert len(fs) == 1
    f = fs[0]
    assert f.severity == "HIGH"
    assert f.file == "src/foo.py"
    assert f.line == 42
    assert "eval" in f.message


def test_parse_finding_line_with_line_keyword():
    fs = RP.parse_findings("auth.py line 10: secret hardcoded")
    assert len(fs) == 1
    assert fs[0].file == "auth.py"
    assert fs[0].line == 10
    assert fs[0].severity == "MEDIUM"  # default when no tag


def test_parse_explicit_security_tag():
    fs = RP.parse_findings("SECURITY: payments.py:5 path traversal possible")
    assert fs[0].severity == "HIGH"
    assert fs[0].file == "payments.py"
    assert fs[0].line == 5


def test_parse_no_findings_returns_empty():
    fs = RP.parse_findings("[openai] KEINE FUNDE\n[hf] looks clean to me")
    assert fs == []


def test_parse_dedup_identical_lines():
    text = ("[HIGH] a.py:1 x\n" * 3)
    fs = RP.parse_findings(text)
    assert len(fs) == 1


def test_max_severity():
    fs = [RP.Finding(severity="LOW"), RP.Finding(severity="HIGH"),
          RP.Finding(severity="MEDIUM")]
    assert RP.max_severity(fs) == "HIGH"
    assert RP.max_severity([]) == "INFO"


def test_severity_to_labels_high():
    fs = [RP.Finding(severity="HIGH", file="a.py", line=1,
                     message="token leak in log")]
    labels = RP.severity_to_labels(fs)
    assert "BUG" in labels
    assert "HIGH" in labels
    assert "SECURITY" in labels  # "leak" triggers the security label


def test_severity_to_labels_clean():
    assert RP.severity_to_labels([]) == []


def test_severity_to_labels_medium_low():
    fs = [RP.Finding(severity="MEDIUM"), RP.Finding(severity="LOW")]
    labels = RP.severity_to_labels(fs)
    assert "MEDIUM" in labels
    assert "LOW" in labels
    assert "BUG" not in labels


def test_review_cache_roundtrip(tmp_path, monkeypatch):
    cache = tmp_path / ".review_cache.json"
    monkeypatch.setattr(RC, "CACHE_FILE", str(cache))
    assert RC.get("o/r", "1", 0, "chunkA") is None
    RC.put("o/r", "1", 0, "chunkA", "[hf] KEINE FUNDE")
    assert RC.get("o/r", "1", 0, "chunkA") == "[hf] KEINE FUNDE"
    # different chunk -> miss
    assert RC.get("o/r", "1", 0, "chunkB") is None
    # file perms are restrictive (0600) when under ~/.idun; here it is tmp
    assert cache.exists()


def test_review_cache_clear(tmp_path, monkeypatch):
    cache = tmp_path / ".review_cache.json"
    monkeypatch.setattr(RC, "CACHE_FILE", str(cache))
    RC.put("o/r", "1", 0, "c", "x")
    assert cache.exists()
    RC.clear()
    assert not cache.exists()


def test_chunk_text_parsing_extracts_findings_across_providers():
    # Simulate the merged chunk text produced by _review_one_chunk.
    chunk_text = _sample_review_text("openai") + "\n" + _sample_review_text("hf")
    findings = []
    for line in chunk_text.splitlines():
        if line.startswith("["):
            end = line.find("]")
            provider = line[1:end]
            rest = line[end + 1:]
            for f in RP.parse_findings(rest):
                findings.append(f.with_source(provider))
        else:
            findings.extend(RP.parse_findings(line))
    # 2 providers x (1 HIGH + 1 MEDIUM) = 4 findings, KEINE FUNDE lines drop out
    assert len(findings) == 4
    assert all(f.source in ("openai", "hf") for f in findings)
    highs = [f for f in findings if f.severity == "HIGH"]
    assert len(highs) == 2
    assert all(f.file == "src/auth.py" and f.line == 42 for f in highs)

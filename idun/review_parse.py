"""Parse self-built review output into structured findings.

The reviewer (`idun-multi review`) asks several LLM providers to find real
problems in a PR diff. Each provider returns free text. To turn that into
actionable artifacts (severity labels, inline PR comments) we parse the text
into :class:`Finding` objects.

This module is pure / offline — no network, no LLM. It is unit-tested in
``tests/test_review.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# Severity levels, ordered worst -> best.
SEVERITY_ORDER = ("HIGH", "MEDIUM", "LOW", "INFO")
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}

# Mapping from a free-text severity hint to our canonical level.
_SEVERITY_WORDS = {
    "CRITICAL": "HIGH", "CRIT": "HIGH", "HIGH": "HIGH", "SECURITY": "HIGH",
    "SEC": "HIGH", "BUG": "HIGH", "BLOCKER": "HIGH",
    "MEDIUM": "MEDIUM", "MED": "MEDIUM", "WARN": "MEDIUM", "WARNING": "MEDIUM",
    "LOW": "LOW", "NIT": "LOW", "MINOR": "LOW", "TRIVIAL": "LOW",
    "INFO": "INFO", "INFORMATIONAL": "INFO", "NOTE": "INFO", "STYLE": "INFO",
}

# Patterns for "file:line" or "file line" with optional leading severity tag.
# Examples handled:
#   src/foo.py:42  use of eval is unsafe
#   [HIGH] src/foo.py:42 use of eval is unsafe
#   SECURITY: auth.py:10 token leaked
#   src/foo.py line 42: something
#   KEINE FUNDE / no findings / looks clean
_LINE_RE = re.compile(
    r"""
    (?P<sevtag>\[?(?:HIGH|MEDIUM|LOW|INFO|CRITICAL|CRIT|SECURITY|SEC|BUG|
                     BLOCKER|MED|WARN|WARNING|NIT|MINOR|TRIVIAL|
                     INFORMATIONAL|NOTE|STYLE)\]?[:\s-]*)?
    (?P<path>[A-Za-z0-9_./\-]+\.[A-Za-z0-9]{1,5})
    (?:[:\s]+line\s+|\s*[:\s]+\s*)
    (?P<line>\d+)
    \s*:?\s*
    (?P<msg>.*)
    """,
    re.VERBOSE,
)


@dataclass
class Finding:
    """A single review finding extracted from provider text."""

    severity: str = "MEDIUM"
    file: str = ""
    line: int | None = None
    message: str = ""
    source: str = ""  # which provider produced it (filled by caller)

    def with_source(self, source: str) -> "Finding":
        if self.source:
            return self
        self.source = source
        return self


def _normalize_severity(hint: str | None) -> str:
    if not hint:
        return "MEDIUM"
    token = hint.strip("[]: \t-").upper()
    return _SEVERITY_WORDS.get(token, "MEDIUM")


def parse_findings(text: str) -> list[Finding]:
    """Parse free-text review output into a list of findings.

    Lines that look like ``path:line message`` (with an optional leading
    severity tag) become :class:`Finding` objects. Everything else is kept as
    a single free-form finding only if it reads like a concrete problem
    (heuristic: contains a path-like token). Pure prose with no path is
    returned as one INFO finding so callers still see the raw verdict.
    """
    findings: list[Finding] = []
    if not text:
        return findings

    kept_prose: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if m:
            findings.append(Finding(
                severity=_normalize_severity(m.group("sevtag")),
                file=m.group("path"),
                line=int(m.group("line")),
                message=(m.group("msg") or "").strip(),
            ))
        else:
            # Keep non-matching lines; they may carry the verdict.
            kept_prose.append(line)

    if not findings and kept_prose:
        joined = " ".join(kept_prose)
        if re.search(r"keine funde|no findings|looks? clean|sauber|nothing",
                     joined, re.IGNORECASE):
            return []  # explicit "clean" verdict
        findings.append(Finding(severity="INFO", message=joined[:500]))

    # de-dup identical (file, line, message)
    seen = set()
    uniq: list[Finding] = []
    for f in findings:
        key = (f.file, f.line, f.message.lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq


def max_severity(findings: Iterable[Finding]) -> str:
    """Return the worst severity present, or INFO when empty."""
    worst = "INFO"
    for f in findings:
        if SEVERITY_RANK.get(f.severity, 9) < SEVERITY_RANK.get(worst, 9):
            worst = f.severity
    return worst


def severity_to_labels(findings: Iterable[Finding]) -> list[str]:
    """Map findings to GitHub labels (highest severity class wins).

    Returns a deterministic, sorted label list. Example:
    findings with one HIGH bug -> ["BUG", "HIGH"].
    """
    if not findings:
        return []
    labels = set()
    for f in findings:
        sev = f.severity
        if sev == "HIGH":
            labels.update({"BUG", "HIGH"})
            if "SECURITY" in f.message.upper() or "LEAK" in f.message.upper():
                labels.add("SECURITY")
        elif sev == "MEDIUM":
            labels.update({"REVIEW", "MEDIUM"})
        elif sev == "LOW":
            labels.update({"LOW"})
        else:  # INFO
            labels.update({"INFO"})
    return sorted(labels)

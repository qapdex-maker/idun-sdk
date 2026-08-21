"""Version metadata must have exactly one source of truth.

Why this file exists
--------------------
The project carried the version in four places and they had already drifted:

    idun/__init__.py   __version__ = "1.0.22"   <- correct
    pyproject.toml     version = "1.0.22"       <- duplicated by hand
    setup.py           VERSION = _read_version()
    idun_multi.py      VERSION = "0.2.6"        <- STALE, four minors behind

``idun-multi --version`` and ``idun-multi doctor`` therefore reported 0.2.6 to
users running 1.0.22. A wrong version in a bug report sends everyone hunting in
the wrong release.

This duplication is also what caused the packaging regression (B1): entry_points
lived only in setup.py while pyproject.toml owned [project], so they were
ignored. Metadata kept in two places drifts; metadata kept in four places is
guaranteed to be wrong somewhere.

Contract: ``idun.__version__`` is the single source. Everything else must
either read from it or match it exactly.
"""
from __future__ import annotations

import os
import re

import pytest

import idun

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str) -> str:
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not present in this checkout")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_canonical_version_is_sane():
    """idun.__version__ is the source of truth and must look like a version."""
    assert re.fullmatch(r"\d+\.\d+\.\d+\S*", idun.__version__), (
        f"unexpected version format: {idun.__version__!r}"
    )


def test_idun_multi_version_matches_package():
    """idun-multi must not report a stale hardcoded version.

    Before the fix idun_multi.py had VERSION = "0.2.6" while the package was
    1.0.22, so `idun-multi --version` and `idun-multi doctor` both lied.
    """
    src = _read("idun_multi.py")
    literals = re.findall(r'^VERSION\s*=\s*["\']([^"\']+)["\']', src, re.MULTILINE)
    for lit in literals:
        assert lit == idun.__version__, (
            f"idun_multi.py hardcodes VERSION = {lit!r} but the package is "
            f"{idun.__version__!r}. Import it from idun instead of copying it."
        )


def test_pyproject_version_matches_package():
    """pyproject.toml must agree with the package version."""
    src = _read("pyproject.toml")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', src, re.MULTILINE)
    if match is None:
        # dynamic version is the better setup -- nothing to compare
        assert "dynamic" in src, (
            "pyproject.toml declares neither a static version nor a dynamic one"
        )
        return
    assert match.group(1) == idun.__version__, (
        f"pyproject.toml says {match.group(1)!r}, package says "
        f"{idun.__version__!r}. Prefer a dynamic version read from "
        f"idun.__version__ so the two cannot drift."
    )


def test_cli_modules_do_not_duplicate_version():
    """No CLI module may define its own version literal.

    Generic guard: catches the next copy-paste before it drifts, in any of the
    three top-level CLI modules.
    """
    offenders = []
    for name in ("idun_cli.py", "idun_multi.py", "idun_mcp.py"):
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        for lit in re.findall(
            r'^(?:VERSION|__version__)\s*=\s*["\']([^"\']+)["\']',
            src,
            re.MULTILINE,
        ):
            if lit != idun.__version__:
                offenders.append(f"{name}: {lit!r}")
    assert not offenders, (
        "CLI modules define their own version literal, which will drift from "
        f"idun.__version__ ({idun.__version__!r}): {offenders}. Import the "
        "version instead."
    )

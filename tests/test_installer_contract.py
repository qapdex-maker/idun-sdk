"""The installer must fail loudly instead of leaving a broken install.

Why this file exists
--------------------
Two independent ways install.sh could report success while leaving the user
with something unusable:

1. ``setuptools`` was never checked. Python 3.12+ no longer ships it, and
   Python 3.14 (Termux) definitely does not, so ``pip install -e`` fails with a
   raw ``ModuleNotFoundError`` traceback. install.sh only verified python3 and
   pip. This is a plausible cause of the pip failures reported from a fresh
   device.

2. The post-install console-script report was cosmetic. It printed
   ``(not on PATH)`` for a missing script and then exited 0 with a cheerful
   "Next:" message. That is exactly how 1.0.17-1.0.22 shipped with no working
   commands: the installer said everything was fine.

These are static checks on the shell source -- they need no shell execution and
run everywhere, including on Windows.
"""
from __future__ import annotations

import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_SH = os.path.join(ROOT, "install.sh")


@pytest.fixture(scope="module")
def script() -> str:
    if not os.path.exists(INSTALL_SH):
        pytest.skip("install.sh not present in this checkout")
    with open(INSTALL_SH, encoding="utf-8") as fh:
        return fh.read()


def test_installer_checks_setuptools(script):
    """setuptools must be verified before pip install is attempted.

    Without it the user gets ModuleNotFoundError from the build backend rather
    than an actionable message.
    """
    assert re.search(r"\bsetuptools\b", script), (
        "install.sh never mentions setuptools, yet the build backend requires "
        "it (pyproject.toml: requires = [\"setuptools>=61.0\", \"wheel\"]). "
        "Python 3.12+ does not bundle it."
    )


def test_setuptools_check_precedes_install(script):
    """The check has to happen before the install, or it is pointless."""
    if "setuptools" not in script:
        pytest.fail("install.sh does not check setuptools at all")
    first_setuptools = script.index("setuptools")
    install_match = re.search(r"^\s*pip install", script, re.MULTILINE)
    assert install_match, "install.sh contains no 'pip install' line"
    assert first_setuptools < install_match.start(), (
        "the setuptools check appears after 'pip install', so the install "
        "still fails with a raw traceback"
    )


def test_installer_fails_when_console_scripts_are_missing(script):
    """A missing console script must be a hard error, not a printed note.

    The original loop printed "(not on PATH)" and exited 0. An installer that
    reports success on a broken install is how the packaging regression reached
    users.
    """
    assert "idun-mcp" in script, "installer no longer reports the console scripts"
    # Only look *after* the install step: exit 1 in the pre-flight dependency
    # checks says nothing about post-install verification.
    install_match = re.search(r"^\s*pip install", script, re.MULTILINE)
    assert install_match, "install.sh contains no 'pip install' line"
    tail = script[install_match.end():]
    assert re.search(r"exit\s+1", tail), (
        "install.sh never exits non-zero after installing, so a missing "
        "console script is only printed as a note and the installer still "
        "reports success. It must fail on a broken install."
    )


def test_installer_still_uses_no_deps(script):
    """The project is stdlib-only; the install must not pull dependencies."""
    assert "--no-deps" in script, (
        "install.sh should keep --no-deps so a stdlib-only package cannot "
        "silently acquire third-party dependencies"
    )


def test_installer_is_strict_shell(script):
    """``set -eu`` must stay: a silent failure mid-script is unacceptable."""
    assert re.search(r"^set -eu", script, re.MULTILINE), (
        "install.sh must run with 'set -eu' so an unexpected failure aborts"
    )

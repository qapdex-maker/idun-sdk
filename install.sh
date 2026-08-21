#!/bin/sh
# Installer for idun-sdk (stdlib-only; no third-party runtime deps).
#
# Checks the environment first, then installs the package (editable so the
# console scripts track the source tree) and finally VERIFIES that the console
# scripts really exist -- failing with a non-zero exit if they do not.
#
# That last part is not cosmetic. Versions 1.0.17-1.0.22 installed with no
# working commands at all ("command not found" for idun / idun-multi /
# idun-mcp) because pyproject.toml gained a [project] table without
# [project.scripts], which makes PEP 621 ignore the entry_points in setup.py.
# The old installer printed "(not on PATH)" and still exited 0, so a completely
# broken install looked successful. Never again: a missing script is a failure.
#
# Covered by tests/test_installer_contract.py and
# tests/test_packaging_contract.py.
set -eu

REPO="$(cd "$(dirname "$0")" && pwd)"
MIN_PY=3.8

echo "== idun-sdk installer =="
echo "repo: $REPO"

# --- dependency checks -----------------------------------------------------
need() { command -v "$1" >/dev/null 2>&1 || { echo "MISSING: $1"; exit 1; }; }
need python3
need pip

py=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
ok=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 8) else 0)")
if [ "$ok" -ne 1 ]; then
    echo "Python >= $MIN_PY required (found $py)"
    exit 1
fi
echo "python: $py  (>= $MIN_PY OK)"

# setuptools is the build backend (pyproject.toml: setuptools>=61.0) and is NOT
# bundled with Python 3.12+. Without this check the install dies on a raw
# ModuleNotFoundError from the backend, which is what happened on a fresh
# Termux/Android device running Python 3.14.
if python3 -c 'import setuptools' >/dev/null 2>&1; then
    sv=$(python3 -c 'import setuptools; print(setuptools.__version__)' 2>/dev/null || echo "?")
    echo "setuptools: $sv (OK)"
else
    echo ""
    echo "MISSING: setuptools -- required to build this package."
    echo "Python 3.12+ no longer bundles it."
    echo ""
    echo "Install it first:"
    echo "    pip install setuptools"
    echo ""
    echo "Recommended (keeps your system Python clean):"
    echo "    python3 -m venv .venv && . .venv/bin/activate"
    echo "    pip install setuptools"
    exit 1
fi

# build is optional: a wheel makes a cleaner install, but pip can install the
# source tree directly if build is unavailable.
if python3 -m build --version >/dev/null 2>&1; then
    echo "build : available"
else
    echo "build : not installed (pip will install from source tree directly)"
fi

# --- install ---------------------------------------------------------------
echo "installing idun-sdk ..."
pip install -e "$REPO" --no-deps

# --- post-install verification ---------------------------------------------
# A console script that is declared but not on PATH means the install is
# unusable. Report every script, then fail if any is missing.
echo ""
echo "== installed console scripts =="
missing=0
for s in idun idun-multi idun-mcp; do
    if p=$(command -v "$s" 2>/dev/null); then
        echo "  $s -> $p"
    else
        echo "  $s -> MISSING (not on PATH)"
        missing=$((missing + 1))
    fi
done

if [ "$missing" -ne 0 ]; then
    echo ""
    echo "INSTALL FAILED: $missing console script(s) were not installed."
    echo ""
    echo "This is the 1.0.17-1.0.22 packaging regression. Check that"
    echo "pyproject.toml contains a [project.scripts] table -- a [project]"
    echo "table without it makes setuptools ignore entry_points in setup.py."
    echo ""
    echo "If you installed into a virtualenv, make sure it is activated."
    exit 1
fi

echo ""
echo "All console scripts installed."
echo "Next: run ./test.sh for post-install verification (scripts resolve to"
echo "this package + offline suite is green). Then: idun-multi doctor"

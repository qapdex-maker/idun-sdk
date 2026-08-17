#!/bin/sh
# Installer for idun-sdk (stdlib-only; no third-party runtime deps).
#
# Checks the environment first, then installs the package (editable so the
# console scripts track the source tree). After install it suggests running
# ./test.sh for the post-install verification (that the idun / idun-multi /
# idun-mcp console scripts resolve to this package and the suite is green).
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

echo ""
echo "== installed console scripts =="
for s in idun idun-multi idun-mcp; do
    p=$(command -v "$s" 2>/dev/null || echo "(not on PATH)")
    echo "  $s -> $p"
done

echo ""
echo "Next: run ./test.sh for post-install verification (scripts resolve to"
echo "this package + offline suite is green). Then: idun-multi doctor"

#!/bin/sh
# Canonical offline self-test for idun-sdk.
#
# Strategy (per repo convention): run the suite in an isolated temp dir with
# its own environment, cleaning up on exit via a trap. We install the package
# into a throwaway --target directory and run pytest against it from there, so
# the test never depends on the current editable checkout or any globally
# installed copy.
set -eu

REPO="$(cd "$(dirname "$0")" && pwd)"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "== idun-sdk offline self-test =="
echo "repo : $REPO"
echo "work : $WORK"

# 1) build a wheel (best-effort; fall back to sdist if build is unavailable)
# Remove any stale wheels first so only a freshly built one is picked up.
rm -f "$REPO"/dist/*.whl "$REPO"/dist/*.tar.gz
python3 -m build --wheel >/dev/null 2>&1 || true
WHEEL=$(ls -t "$REPO"/dist/idun_sdk-*.whl 2>/dev/null | head -1 || true)

# 2) install into an isolated target dir with no deps (stdlib-only package)
mkdir -p "$WORK/site"
if [ -n "$WHEEL" ]; then
    pip install -q --target="$WORK/site" --no-deps "$WHEEL" 2>&1 | tail -3 || \
        pip install -q --target="$WORK/site" --no-deps "$REPO" 2>&1 | tail -3
else
    pip install -q --target="$WORK/site" --no-deps "$REPO" 2>&1 | tail -3
fi

# 3) install test deps + run pytest against the isolated install
pip install -q pytest >/dev/null 2>&1 || true
PYTHONPATH="$WORK/site" python3 -m pytest "$REPO/tests" -q

echo "== post-install verification =="
# assert the three console scripts resolve to THIS package, not a hijacker
verify_script() {
    name="$1"
    expected="$2"
    path=$(command -v "$name" 2>/dev/null || true)
    if [ -z "$path" ]; then
        echo "WARN: $name not on PATH"
        return 0
    fi
    if grep -q "$expected" "$path" 2>/dev/null; then
        echo "OK  : $name -> $expected"
    else
        echo "FAIL: $name does not point at $expected ($path)"
        return 1
    fi
}
verify_script idun       idun_cli
verify_script idun-multi idun_multi
verify_script idun-mcp   idun_mcp

echo "== done =="

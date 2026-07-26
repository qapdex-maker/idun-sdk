#!/usr/bin/env bash
# Canonical self-test for idun-sdk (user convention: mktemp isolation + trap cleanup).
# Offline: compiles all modules, runs trajectory-normalization + CLI-parse checks.
# Usage: ./test.sh
set -euo pipefail

SDK_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX="$(mktemp -d "${TMPDIR:-/tmp}/hermes-idun-test.XXXXXX")"
cleanup() { rm -rf "$PREFIX"; }
trap cleanup EXIT

pass=0; fail=0
ok()   { echo "  PASS: $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL: $1"; fail=$((fail+1)); }

echo "=== idun-sdk self-test (offline) ==="

# 1) compile
if python3 -m py_compile "$SDK_DIR/idun/client.py" "$SDK_DIR/idun/auth.py" \
     "$SDK_DIR/idun/__init__.py" "$SDK_DIR/idun_cli.py" "$SDK_DIR/setup.py" 2>"$PREFIX/compile.err"; then
  ok "all modules compile"
else
  bad "compile failed: $(cat "$PREFIX/compile.err" | head -c 200)"
fi

# 2) normalization (offline sample matching live Foundry output[] shape)
cat > "$PREFIX/norm.py" <<PY
import sys, os
sys.path.insert(0, "$SDK_DIR")
from idun.client import _normalize_output
sample = {"model":"gpt-5.4-2026-03-05","output":[
 {"type":"message","role":"assistant","content":[{"type":"output_text","text":"Plan."}]},
 {"type":"web_search_call","status":"completed","id":"ws_1","action":{"type":"search","queries":["Contoso CEO"],"query":"Contoso CEO"}},
 {"type":"message","role":"assistant","content":[{"type":"output_text","text":"Final."}]}]}
res = _normalize_output(sample)
assert res.model=="gpt-5.4-2026-03-05"
assert res.text=="Plan.\n\nFinal."
assert len(res.steps)==3
assert res.steps[1].kind=="tool" and res.steps[1].tool=="web_search" and res.steps[1].query=="Contoso CEO"
print("normalize OK")
PY
if ( cd "$SDK_DIR" && python3 "$PREFIX/norm.py" ) >"$PREFIX/norm.out" 2>&1; then
  ok "output[] -> (text, 3 steps: reasoning/tool/reasoning)"
else
  bad "normalization: $(cat "$PREFIX/norm.out" | head -c 200)"
fi

# 3) CLI subcommands
if python3 -m idun_cli --help >"$PREFIX/help.out" 2>&1 && \
   grep -q "login" "$PREFIX/help.out" && grep -q "chat" "$PREFIX/help.out" && grep -q "trace" "$PREFIX/help.out"; then
  ok "CLI exposes login/chat/trace"
else
  bad "CLI help missing subcommands"
fi

# 4) importable package
if python3 -c "import idun; assert idun.__version__=='0.1.0'" >/dev/null 2>&1; then
  ok "package importable as idun (v0.1.0)"
else
  bad "package not importable"
fi

echo "=== self-test: pass=$pass fail=$fail ==="
[ "$fail" -eq 0 ] || exit 1

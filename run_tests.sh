#!/bin/sh
# run_tests.sh — robust local pytest runner for idun-sdk.
#
# Why: running pytest from ~ (home) walks foreign source trees
# (chromium/qt under ~/storage) and a SystemExit in unrelated third-party
# tests crashes the whole collection (see pytest.log: 996 items, 276 errors,
# 10 min hang). This script pins cwd to the repo, ignores foreign dirs, and
# exits cleanly on failure.
set -e

# Always operate from this script's directory (the repo root).
cd "$(dirname "$0")"

# Defensive: ignore anything outside tests/ so a stray foreign test file
# anywhere on the filesystem cannot crash the run.
ignore_args=""
for d in /data/data/com.termux/files/home/storage \
         /data/data/com.termux/files/home/.cache \
         /data/data/com.termux/files/home/.hermes \
         /data/data/com.termux/files/home/repo ; do
  [ -d "$d" ] && ignore_args="$ignore_args --ignore=$d"
done

echo "Running pytest from: $(pwd)"
echo "Command: python3 -m pytest tests/ -q $ignore_args"
exec python3 -m pytest tests/ -q -p no:cacheprovider $ignore_args

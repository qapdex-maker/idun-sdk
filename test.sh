#!/bin/sh
# Canonical offline self-test for idun-sdk.
# Runs pytest (no network; exercises normalization, export, CLI, logo, rotation).
set -e
cd "$(dirname "$0")"
python3 -m pytest -q

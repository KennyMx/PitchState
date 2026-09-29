#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3.10}"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
.venv/bin/python scripts/download_assets.py --models
printf '%s\n' 'Models installed. Set JEV_API_KEY in .env.local, then run npm run server.'

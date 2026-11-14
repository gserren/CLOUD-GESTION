#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
if command -v node >/dev/null 2>&1; then
  node --check frontend/app.js
  node --check frontend/report.js
fi

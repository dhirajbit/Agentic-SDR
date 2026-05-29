#!/usr/bin/env bash
# Launch the Best Roadways SDR control panel.
#
#   tenants/best-roadways/run_panel.sh
#
# Opens a local web app at http://127.0.0.1:8765 — config panel, CSV upload
# (Gemini analysis), SDR/Observer cycle runners, and live logs.

set -euo pipefail

TENANT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$TENANT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

export AGENTIC_SDR_TENANT=best-roadways

# Ensure deps (quiet, idempotent).
python -c "import flask, google.genai, dotenv, requests" 2>/dev/null || \
  pip install -q -r "$TENANT_DIR/requirements.txt"

exec python "$TENANT_DIR/app.py"

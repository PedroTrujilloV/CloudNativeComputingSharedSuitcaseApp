#!/usr/bin/env bash
# ============================================================
# Creates a shared Python venv for the no-Docker local verification.
#
# All 8 apps (users, posts, offers, routes, scores, rf003, rf004,
# rf005) run from this single venv with PYTHONPATH=<app>/src and
# DB_DRIVER=sqlite (in-memory), so the only runtime dependencies are
# the ones every app already uses:
#   fastapi, uvicorn, pydantic, pydantic-settings, python-dotenv,
#   sqlalchemy, httpx
# (psycopg is NOT needed: sqlite is used for the local databases).
#
# Usage:
#   bash scripts/no_docker/setup_venv.sh /path/to/venv
# ============================================================
set -euo pipefail

VENV_DIR="${1:-${REPO_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}/.local-verify-venv}"

if [ -x "${VENV_DIR}/bin/python" ]; then
  echo "    venv already exists at ${VENV_DIR}"
  exit 0
fi

echo "    creating venv at ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet \
  "fastapi==0.115.12" \
  "uvicorn==0.27.1" \
  "pydantic==2.6.1" \
  "pydantic-settings==2.1.0" \
  "python-dotenv==1.0.1" \
  "sqlalchemy==2.0.36" \
  "httpx==0.28.1"
echo "    venv ready: $(${VENV_DIR}/bin/python --version 2>&1)"

#!/usr/bin/env bash
# Restart only the rf005 orchestrator (picks up code changes).
# All other services must already be running (see start_rf005_services.sh).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pkill -f "entrypoints.api.main:app --host 127.0.0.1 --port 8005" 2>/dev/null || true
sleep 1
cd "$ROOT/rf005_query_post_app"
env USERS_SERVICE_URL=http://localhost:8000 \
    POSTS_SERVICE_URL=http://localhost:8002 \
    ROUTES_SERVICE_URL=http://localhost:8006 \
    OFFERS_SERVICE_URL=http://localhost:8003 \
    SCORES_SERVICE_URL=http://localhost:8004 \
    PYTHONPATH="$ROOT/rf005_query_post_app/src" \
  nohup poetry run uvicorn entrypoints.api.main:app --host 127.0.0.1 --port 8005 \
  >> /tmp/rf005_logs/rf005.log 2>&1 &
echo "rf005 restarted pid $!"

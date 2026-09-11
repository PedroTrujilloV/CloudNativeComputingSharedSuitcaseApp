#!/usr/bin/env bash
# Start all services needed by scripts/rf005_manual_verification.sh
# (users, routes, posts, offers, scores, rf003, rf005) with file-backed
# sqlite databases. Logs go to /tmp/rf005_logs/.
# Run this once before the verification script; it does NOT stop them.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR=/tmp/rf005_logs
mkdir -p "$LOGDIR"
rm -f /tmp/rf005_verify_*.db

start_app() {
  local name="$1" dir="$2" port="$3"; shift 3
  (
    cd "$ROOT/$dir" || exit 1
    env "$@" DB_DRIVER=sqlite PYTHONPATH="$(pwd)/src" \
      poetry run uvicorn entrypoints.api.main:app \
      --host 127.0.0.1 --port "$port" >>"$LOGDIR/$name.log" 2>&1 &
    echo "$name pid $! (port $port)"
  )
}

start_app users  users_app 8000 SQLITE_URL="sqlite:////tmp/rf005_verify_users.db"
start_app routes routes_app 8006 SQLITE_URL="sqlite:////tmp/rf005_verify_routes.db"
start_app posts  posts_app  8002 SQLITE_URL="sqlite:////tmp/rf005_verify_posts.db"
start_app offers offers_app 8003 SQLITE_URL="sqlite:////tmp/rf005_verify_offers.db"
start_app scores scores_app 8004 SQLITE_URL="sqlite:////tmp/rf005_verify_scores.db"

# Orchestrators: no DB of their own
(
  cd "$ROOT/rf003_create_post_app"
  env USERS_SERVICE_URL=http://localhost:8000 \
      ROUTES_SERVICE_URL=http://localhost:8006 \
      POSTS_SERVICE_URL=http://localhost:8002 \
      PYTHONPATH="$(pwd)/src" \
    poetry run uvicorn entrypoints.api.main:app --host 127.0.0.1 --port 8001 \
    >>"$LOGDIR/rf003.log" 2>&1 &
  echo "rf003 pid $! (port 8001)"
)
(
  cd "$ROOT/rf005_query_post_app"
  env USERS_SERVICE_URL=http://localhost:8000 \
      POSTS_SERVICE_URL=http://localhost:8002 \
      ROUTES_SERVICE_URL=http://localhost:8006 \
      OFFERS_SERVICE_URL=http://localhost:8003 \
      SCORES_SERVICE_URL=http://localhost:8004 \
      PYTHONPATH="$(pwd)/src" \
    poetry run uvicorn entrypoints.api.main:app --host 127.0.0.1 --port 8005 \
    >>"$LOGDIR/rf005.log" 2>&1 &
  echo "rf005 pid $! (port 8005)"
)

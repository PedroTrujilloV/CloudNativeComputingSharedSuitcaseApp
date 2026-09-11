#!/usr/bin/env bash
# ============================================================
# MISO — Local verification WITHOUT Docker/Minikube
#
# Runs all 8 apps directly from source (Python + in-memory
# SQLite), starts the local ingress proxy (scripts/no_docker/
# ingress_proxy.py) on 127.0.0.1:8080, and executes the
# Postman collections from scripts/entrega2/ with Newman:
#
#   * Functional:  evaluate_rf003/4/5.json (all apps up)
#   * Consistency: evaluate_rf003/4/5_consistency.json
#     — the "app down" scenarios kill the corresponding
#       uvicorn process, so the proxy answers 503 exactly
#       like the real ingress with no ready endpoints.
#     App combinations mirror scripts/entrega2/ci_evaluador_entrega2.yml.
#
# Usage:
#   bash scripts/local-verify-no-docker.sh
#
# Env overrides:
#   PROXY_PORT  (default 8080)
#   VENV_DIR    (default <repo>/.local-verify-venv)
# ============================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PROXY_PORT="${PROXY_PORT:-8080}"
BASE_PATH="http://127.0.0.1:${PROXY_PORT}"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.local-verify-venv}"
VENV_PY="$VENV_DIR/bin/python"
VENV_UVICORN="$VENV_DIR/bin/uvicorn"

# Port map (same as k8s_entrega2 services)
PORT_USERS=8000
PORT_POSTS=8001
PORT_OFFERS=8002
PORT_ROUTES=8003
PORT_SCORES=8004
PORT_RF003=8005
PORT_RF004=8006
PORT_RF005=8007

PASS=0
FAIL=0
TMP_DIR="$(mktemp -d /tmp/miso-no-docker.XXXXXX)"
LOG_DIR="$TMP_DIR/logs"
mkdir -p "$LOG_DIR"

# ---------- helpers (bash 3.2 compatible: no associative arrays) ----------
app_port() {
    case "$1" in
        users) echo $PORT_USERS;; posts) echo $PORT_POSTS;;
        offers) echo $PORT_OFFERS;; routes) echo $PORT_ROUTES;;
        scores) echo $PORT_SCORES;; rf003) echo $PORT_RF003;;
        rf004) echo $PORT_RF004;; rf005) echo $PORT_RF005;;
    esac
}
app_src() {
    case "$1" in
        users) echo "users_app/src";; posts) echo "posts_app/src";;
        offers) echo "offers_app/src";; routes) echo "routes_app/src";;
        scores) echo "scores_app/src";; rf003) echo "rf003_create_post_app/src";;
        rf004) echo "rf004_create_offer_app/src";; rf005) echo "rf005_query_post_app/src";;
    esac
}

check() {
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo "  ✅ $desc"; PASS=$((PASS+1))
    else
        echo "  ❌ $desc"; FAIL=$((FAIL+1))
    fi
}

http_code() {
    # curl -w always prints the code (000 on connection failure), even when
    # it exits non-zero. Do NOT append "|| echo 000": it would produce the
    # doubled string "000000" which never equals "000".
    curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$@" 2>/dev/null
}

log() { echo; echo "── $* ──────────────────────────────────────────"; }

# ---------- preflight ----------
log "Preflight"
if ! command -v newman >/dev/null 2>&1; then
    echo "❌ newman no está instalado (npm i -g newman). Abortando."; exit 1
fi
echo "  newman $(newman --version)"

if [ ! -x "$VENV_PY" ]; then
    echo "  Creando venv en $VENV_DIR ..."
    bash scripts/no_docker/setup_venv.sh "$VENV_DIR"
fi
check "venv tiene dependencias (fastapi/uvicorn/sqlalchemy)" \
    "$VENV_PY" -c "import fastapi, uvicorn, sqlalchemy, httpx, pydantic_settings"

# ---------- start an app ----------
# start_app <name> <port> <src-dir> <extra-env...>
start_app() {
    local name="$1" port="$2" src="$3"; shift 3
    local envs=("$@")
    # Launch in the current shell: nohup + & disowns the process from this
    # script's terminal, but the pid written to $name.pid is the uvicorn
    # pid itself, so stop_app/up can manage it (a subshell would leave a
    # stale pid pointing at the dead subshell).
    cd "$REPO_ROOT"
    env PYTHONPATH="$src" DB_DRIVER=sqlite APP_NAME="$name" "${envs[@]}" \
        nohup "$VENV_UVICORN" entrypoints.api.main:app \
        --host 127.0.0.1 --port "$port" \
        >"$LOG_DIR/$name.log" 2>&1 &
    echo $! > "$TMP_DIR/$name.pid"
}

wait_port() {
    local port="$1" tries="${2:-30}"
    for _ in $(seq 1 "$tries"); do
        if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$port/" 2>/dev/null; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

# wait for a specific ping endpoint through the direct port
wait_ping() {
    local name="$1" port="$2" path="$3" tries="${4:-40}"
    local code
    for _ in $(seq 1 "$tries"); do
        code="$(http_code "http://127.0.0.1:$port$path")"
        [ -z "$code" ] && code="000"
        if [ "$code" = "200" ]; then return 0; fi
        sleep 0.5
    done
    return 1
}

# true when nothing is listening on the port (bash 3.2 /dev/tcp)
port_free() {
    if (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; then
        return 1
    fi
    return 0
}

stop_app() {
    local name="$1"
    local pidfile="$TMP_DIR/$name.pid"
    [ -f "$pidfile" ] || return 0
    local pid; pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        for _ in $(seq 1 20); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.2
        done
        kill -9 "$pid" 2>/dev/null
    fi
    # The socket must be released before a restart can re-bind the port,
    # otherwise the new process dies with "Address already in use" while
    # the old one is still draining.
    local port; port="$(app_port "$name")"
    for _ in $(seq 1 50); do
        port_free "$port" && break
        sleep 0.1
    done
}

# ---------- start everything ----------
cleanup() {
    for name in users posts offers routes scores rf003 rf004 rf005; do
        [ -f "$TMP_DIR/$name.pid" ] && kill "$(cat "$TMP_DIR/$name.pid")" 2>/dev/null
    done
    [ -f "$TMP_DIR/proxy.pid" ] && kill "$(cat "$TMP_DIR/proxy.pid")" 2>/dev/null
}
trap cleanup EXIT

log "Subiendo las 8 apps (SQLite in-memory) + proxy :$PROXY_PORT"

start_app users   "$PORT_USERS"   "users_app/src"
start_app posts   "$PORT_POSTS"   "posts_app/src"
start_app offers  "$PORT_OFFERS"  "offers_app/src"
start_app routes  "$PORT_ROUTES"  "routes_app/src"
start_app scores  "$PORT_SCORES"  "scores_app/src"
start_app rf003   "$PORT_RF003"   "rf003_create_post_app/src" \
    USERS_SERVICE_URL="http://127.0.0.1:$PORT_USERS" \
    ROUTES_SERVICE_URL="http://127.0.0.1:$PORT_ROUTES" \
    POSTS_SERVICE_URL="http://127.0.0.1:$PORT_POSTS"
start_app rf004   "$PORT_RF004"   "rf004_create_offer_app/src" \
    USERS_SERVICE_URL="http://127.0.0.1:$PORT_USERS" \
    POSTS_SERVICE_URL="http://127.0.0.1:$PORT_POSTS" \
    ROUTES_SERVICE_URL="http://127.0.0.1:$PORT_ROUTES" \
    OFFERS_SERVICE_URL="http://127.0.0.1:$PORT_OFFERS" \
    SCORES_SERVICE_URL="http://127.0.0.1:$PORT_SCORES"
start_app rf005   "$PORT_RF005"   "rf005_query_post_app/src" \
    USERS_SERVICE_URL="http://127.0.0.1:$PORT_USERS" \
    POSTS_SERVICE_URL="http://127.0.0.1:$PORT_POSTS" \
    ROUTES_SERVICE_URL="http://127.0.0.1:$PORT_ROUTES" \
    OFFERS_SERVICE_URL="http://127.0.0.1:$PORT_OFFERS" \
    SCORES_SERVICE_URL="http://127.0.0.1:$PORT_SCORES"

# proxy (stdlib-only, system python is fine)
(
    cd "$REPO_ROOT"
    PROXY_PORT="$PROXY_PORT" nohup python3 scripts/no_docker/ingress_proxy.py \
        >"$LOG_DIR/proxy.log" 2>&1 &
    echo $! > "$TMP_DIR/proxy.pid"
)

for name in users posts offers routes scores rf003 rf004 rf005; do
    port="$(app_port "$name")"
    check "$name escuchando en :$port" wait_ping "$name" "$port" "/$name/ping"
done

# wait until the proxy actually answers 200 (not just accepting TCP)
for _ in $(seq 1 40); do
    code="$(http_code "http://127.0.0.1:$PROXY_PORT/users/ping")"
    [ "$code" = "200" ] && break
    sleep 0.5
done
check "proxy :$PROXY_PORT encaminando /users/ping" \
    bash -c "[ \"\$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 $BASE_PATH/users/ping)\" = '200' ]"

# ---------- newman runner ----------
# run_newman <label> <file> [newman args...]
run_newman() {
    local label="$1" file="$2"; shift 2
    echo
    echo "▶ newman: $label"
    if newman run "scripts/entrega2/$file" \
        --env-var "BASE_PATH=$BASE_PATH" \
        --reporters cli --reporter-quiet \
        "$@" >"$TMP_DIR/newman-last.log" 2>&1; then
        echo "  ✅ $label"
        PASS=$((PASS+1))
    else
        echo "  ❌ $label (ver $TMP_DIR/newman-last.log)"
        tail -40 "$TMP_DIR/newman-last.log" | sed 's/^/     | /'
        FAIL=$((FAIL+1))
    fi
    cp "$TMP_DIR/newman-last.log" "$TMP_DIR/newman-$(echo "$label" | tr -c 'A-Za-z0-9' '_').log" 2>/dev/null
}

# kill_app / restore helpers for consistency scenarios
down() { echo; echo "  ⏸ bajando $1 ..."; stop_app "$1"; sleep 1; }

start_rf003() { start_app rf003 "$PORT_RF003" "rf003_create_post_app/src" \
    USERS_SERVICE_URL="http://127.0.0.1:$PORT_USERS" \
    ROUTES_SERVICE_URL="http://127.0.0.1:$PORT_ROUTES" \
    POSTS_SERVICE_URL="http://127.0.0.1:$PORT_POSTS"; }
start_rf004() { start_app rf004 "$PORT_RF004" "rf004_create_offer_app/src" \
    USERS_SERVICE_URL="http://127.0.0.1:$PORT_USERS" \
    POSTS_SERVICE_URL="http://127.0.0.1:$PORT_POSTS" \
    ROUTES_SERVICE_URL="http://127.0.0.1:$PORT_ROUTES" \
    OFFERS_SERVICE_URL="http://127.0.0.1:$PORT_OFFERS" \
    SCORES_SERVICE_URL="http://127.0.0.1:$PORT_SCORES"; }
start_rf005() { start_app rf005 "$PORT_RF005" "rf005_query_post_app/src" \
    USERS_SERVICE_URL="http://127.0.0.1:$PORT_USERS" \
    POSTS_SERVICE_URL="http://127.0.0.1:$PORT_POSTS" \
    ROUTES_SERVICE_URL="http://127.0.0.1:$PORT_ROUTES" \
    OFFERS_SERVICE_URL="http://127.0.0.1:$PORT_OFFERS" \
    SCORES_SERVICE_URL="http://127.0.0.1:$PORT_SCORES"; }

up() {
    local name="$1" port src fn
    port="$(app_port "$name")"; src="$(app_src "$name")"
    case "$name" in
        rf003) fn=start_rf003;; rf004) fn=start_rf004;; rf005) fn=start_rf005;;
        *) fn=start_app;;
    esac
    echo "  ▶ subiendo $name ..."
    if [ "$fn" = "start_app" ]; then
        start_app "$name" "$port" "$src"
    else
        "$fn"
    fi
    # wait_ping returns success only when /ping answers 200, so a failed
    # restart (e.g. the port was still busy) is reported instead of being
    # silently treated as up.
    wait_ping "$name" "$port" "/$name/ping" || { echo "  ⚠ $name no respondió (ver $LOG_DIR/$name.log)"; FAIL=$((FAIL+1)); }
}

# ---------- functional (todas las apps arriba) ----------
log "RF003 funcional (todas las apps arriba)"
run_newman "evaluate_rf003" "evaluate_rf003.json"

log "RF004 funcional (todas las apps arriba)"
run_newman "evaluate_rf004" "evaluate_rf004.json"

log "RF005 funcional (todas las apps arriba)"
run_newman "evaluate_rf005" "evaluate_rf005.json"

# ---------- RF003 consistency ----------
log "RF003 consistencia"
run_newman "rf003 consistency: Reset" "evaluate_rf003_consistency.json" --folder "Reset"

# users-app down
down users
run_newman "rf003 consistency: users-app down" "evaluate_rf003_consistency.json" --folder "Test RF-003"
up users
run_newman "rf003 consistency: verificar (users)" "evaluate_rf003_consistency.json" --folder "Verificar Consistencia"

# routes-app down
down routes
run_newman "rf003 consistency: routes-app down" "evaluate_rf003_consistency.json" --folder "RF-003 Crear publicacion"
up routes
run_newman "rf003 consistency: verificar (routes)" "evaluate_rf003_consistency.json" --folder "Verificar Consistencia"

# posts-app down (compensación: la ruta creada debe eliminarse)
down posts
run_newman "rf003 consistency: posts-app down" "evaluate_rf003_consistency.json" --folder "RF-003 Crear publicacion"
up posts
run_newman "rf003 consistency: verificar (posts)" "evaluate_rf003_consistency.json" --folder "Verificar Consistencia"

# ---------- RF004 consistency ----------
log "RF004 consistencia"
run_newman "rf004 consistency: Reset" "evaluate_rf004_consistency.json" --folder "Reset"

# users-app down
down users
run_newman "rf004 consistency: users-app down" "evaluate_rf004_consistency.json" \
    --folder "Test RF-004" --env-var USER_TOKEN=FAKETOKEN \
    --env-var POST_ID=bf8792d2-3097-11ee-be56-0242ac120002
up users
run_newman "rf004 consistency: verificar (users)" "evaluate_rf004_consistency.json" --folder "Verificar Consistencia"

# offers-app down
down offers
run_newman "rf004 consistency: offers-app down" "evaluate_rf004_consistency.json" --folder "RF-004 Crear oferta"
up offers
run_newman "rf004 consistency: verificar (offers)" "evaluate_rf004_consistency.json" --folder "Verificar Consistencia"

# posts-app down (CI: Reset + Crear Recursos ANTES de escalar posts-app a 0)
run_newman "rf004 consistency: Reset" "evaluate_rf004_consistency.json" --folder "Reset"
run_newman "rf004 consistency: Crear Recursos (apps up)" "evaluate_rf004_consistency.json" --folder "Crear Recursos"
down posts
run_newman "rf004 consistency: posts-app down (Sesion & RF-004)" "evaluate_rf004_consistency.json" \
    --folder "Sesion & RF-004" --env-var POST_ID=bf8792d2-3097-11ee-be56-0242ac120002
up posts
run_newman "rf004 consistency: verificar (posts)" "evaluate_rf004_consistency.json" --folder "Verificar Consistencia"

# ---------- RF005 consistency ----------
log "RF005 consistencia"
run_newman "rf005 consistency: Reset" "evaluate_rf005_consistency.json" --folder "Reset"

# users-app down (CI: no hay paso de Verificar Consistencia para este caso)
down users
run_newman "rf005 consistency: users-app down" "evaluate_rf005_consistency.json" \
    --folder "Test RF-005" --env-var USER_TOKEN=FAKETOKEN \
    --env-var POST_ID=bf8792d2-3097-11ee-be56-0242ac120002
up users

# posts-app down (CI: Reset + Crear Recursos ANTES de escalar posts-app a 0)
run_newman "rf005 consistency: Reset" "evaluate_rf005_consistency.json" --folder "Reset"
run_newman "rf005 consistency: Crear Recursos (apps up)" "evaluate_rf005_consistency.json" --folder "Crear Recursos"
down posts
run_newman "rf005 consistency: posts-app down (Sesion & RF-005)" "evaluate_rf005_consistency.json" \
    --folder "Sesion & RF-005" --env-var POST_ID=bf8792d2-3097-11ee-be56-0242ac120002
up posts

# offers-app down (CI: Reset + Crear Recursos ANTES de escalar offers-app a 0;
# sin POST_ID/USER_TOKEN, igual que el CI)
run_newman "rf005 consistency: Reset" "evaluate_rf005_consistency.json" --folder "Reset"
run_newman "rf005 consistency: Crear Recursos (apps up)" "evaluate_rf005_consistency.json" --folder "Crear Recursos"
down offers
run_newman "rf005 consistency: offers-app down (Post & Sesion & RF-005)" "evaluate_rf005_consistency.json" \
    --folder "Post & Sesion & RF-005"
up offers

# ---------- cleanup ----------
log "Limpieza"
for name in users posts offers routes scores rf003 rf004 rf005; do
    stop_app "$name"
done
[ -f "$TMP_DIR/proxy.pid" ] && kill "$(cat "$TMP_DIR/proxy.pid")" 2>/dev/null
# $TMP_DIR se conserva a propósito para poder inspeccionar los logs.

# ---------- summary ----------
echo
echo "════════════════════════════════════════════════════"
echo "  RESUMEN (sin Docker): ${PASS} ✅ / ${FAIL} ❌"
echo "  Logs: $TMP_DIR"
echo "════════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1

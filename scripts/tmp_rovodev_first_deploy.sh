#!/usr/bin/env bash
set -euo pipefail

# tmp_rovodev_: this is a temporary helper script for first-time deployment
# It will: docker compose up, init DB, refresh prompts, init global toolset,
# seed agents, bind toolsets, and run smoke checks.

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
API_URL=${API_URL:-"http://localhost:8000"}
COMPOSE=${COMPOSE:-"docker compose"}

info() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m   $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
err()  { echo -e "\033[1;31m[ERR]\033[0m  $*"; }

wait_for_health() {
  local url="$1"; local tries=60; local delay=2
  info "Waiting for API health at ${url}/health ..."
  for i in $(seq 1 $tries); do
    if curl -sS "${url}/health" | grep -q '"healthy"'; then
      ok "API is healthy"
      return 0
    fi
    sleep "$delay"
  done
  err "API health check failed"; return 1
}

main() {
  info "Starting containers via docker compose"
  (cd "$ROOT_DIR" && $COMPOSE up -d --build)

  wait_for_health "$API_URL"

  info "Initializing database (if needed)"
  # Hitting OpenAPI JSON forces app import; init_db runs at startup
  curl -fsS "${API_URL}/openapi.json" > /dev/null || true

  info "Refreshing prompts"
  if (cd "$ROOT_DIR" && python - <<'PY'
from scripts.refresh_prompts import main as refresh_main
try:
    refresh_main()
    print("OK: refresh_prompts")
except SystemExit:
    print("OK: refresh_prompts (SystemExit)")
except Exception as e:
    print(f"ERR: refresh_prompts {e}")
    raise
PY
  ); then ok "Prompts refreshed"; else err "Prompts refresh failed"; exit 1; fi

  info "Initialize global toolset"
  if curl -fsS -X POST "${API_URL}/api/v1/toolsets/initialize-global" >/dev/null; then
    ok "Global toolset initialized"
  else
    err "Initialize-global failed"; exit 1
  fi

  info "Seeding baseline agents"
  if (cd "$ROOT_DIR" && python - <<'PY'
from api.init_data import initialize_all
from api.database import SessionLocal

db = SessionLocal()
try:
    initialize_all(db)
    print("OK: seed agents")
finally:
    db.close()
PY
  ); then ok "Agents seeded"; else err "Agents seed failed"; exit 1; fi

  info "Binding toolset to first agent (example)"
  # pick the first non-global toolset and first agent, if available
  AGENT_ID=$(curl -fsS "${API_URL}/api/v1/agents" | python - <<'PY'
import sys, json
obj=json.load(sys.stdin)
items=obj.get('items',[])
print(items[0]['id'] if items else '')
PY
)
  TOOLSET_ID=$(curl -fsS "${API_URL}/api/v1/toolsets" | python - <<'PY'
import sys, json
arr=json.load(sys.stdin)
# prefer non-global toolset if exists; else fallback to global
non_globals=[t for t in arr if not t.get('is_global')]
print((non_globals[0]['id'] if non_globals else (arr[0]['id'] if arr else '')))
PY
)
  if [[ -n "$AGENT_ID" && -n "$TOOLSET_ID" ]]; then
    if curl -fsS -X POST "${API_URL}/api/v1/agents/${AGENT_ID}/toolsets" \
      -H 'Content-Type: application/json' \
      -d "{\"agent_id\": \"${AGENT_ID}\", \"toolset_id\": \"${TOOLSET_ID}\"}" >/dev/null; then
      ok "Bound toolset ${TOOLSET_ID} to agent ${AGENT_ID}"
    else
      warn "Binding failed (may already be bound)"
    fi
  else
    warn "No agent or toolset found to bind"
  fi

  info "Running smoke checks"
  if (cd "$ROOT_DIR" && pytest -q scripts/tests/test_smoke_api.py -q); then
    ok "Smoke tests passed"
  else
    err "Smoke tests failed"; exit 1
  fi

  ok "First-time deployment finished"
}

main "$@"

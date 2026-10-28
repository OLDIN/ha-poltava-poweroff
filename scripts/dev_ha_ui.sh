#!/usr/bin/env bash
# Starts a REAL Home Assistant (UI on :8124) with the poltava_poweroff integration,
# talking to a local mock (:8798) instead of energy-ua.info. Fully automatic:
# onboarding, config entry, a dashboard with the card. Lets you "break" the site and see what users see.
#
#   scripts/dev_ha_ui.sh up                 — start everything (HA + mock)
#   scripts/dev_ha_ui.sh mode <ok|nodata|http500|garbage|timeout>
#   scripts/dev_ha_ui.sh refresh            — poll the site now (poltava_poweroff.refresh service)
#   scripts/dev_ha_ui.sh restart            — restart HA only (checks the schedule cache)
#   scripts/dev_ha_ui.sh show               — sensor states
#   scripts/dev_ha_ui.sh shot [name]        — dashboard screenshot -> screenshots/<name>.png
#   scripts/dev_ha_ui.sh readme             — re-take the README screenshots -> pics/*.png
#   scripts/dev_ha_ui.sh down               — stop
#
# Port 8124 avoids a clash with ha-silpo (8123).
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${VENV:-$PWD/.venv-ha}/bin"
CFG="$PWD/ha_config"
PORT_HA="${PORT_HA:-8124}"
PORT_MOCK="${POLTAVA_MOCK_PORT:-8798}"
BASE="http://127.0.0.1:$PORT_HA"
MOCK="http://127.0.0.1:$PORT_MOCK"
GROUP="${GROUP:-4-1}"
export POLTAVA_POWEROFF_BASE_URL=$MOCK POLTAVA_MOCK_PORT=$PORT_MOCK

_pids_on() { lsof -ti :"$1" 2>/dev/null || true; }
_wait_port_free() { for _ in $(seq 1 20); do [ -z "$(_pids_on "$1")" ] && return 0; sleep 1; done; return 1; }
_wait_ha() { for _ in $(seq 1 60); do curl -sf -o /dev/null "$BASE/" 2>/dev/null && return 0; sleep 3; done; return 1; }
_hass_pids() { pgrep -f "hass --config $CFG" || true; }

cmd_up() {
  cmd_down >/dev/null
  rm -rf "$CFG"; mkdir -p "$CFG/custom_components"
  ln -sfn "$PWD/custom_components/poltava_poweroff" "$CFG/custom_components/poltava_poweroff"
  cat > "$CFG/configuration.yaml" <<YAML
# no default_config: faster start, no bluetooth (crashes on macOS on shutdown)
homeassistant:
  name: Poltava (dev)
  latitude: 49.5883
  longitude: 34.5514
  elevation: 150
  unit_system: metric
  time_zone: Europe/Kyiv
  country: UA
  language: uk
frontend:
http:
  server_port: $PORT_HA
api:
config:
history:
logbook:
lovelace:
logger:
  default: warning
  logs:
    custom_components.poltava_poweroff: debug
YAML
  "$VENV/python" scripts/inject_dashboard.py "$CFG"
  POLTAVA_MOCK_PORT=$PORT_MOCK nohup "$VENV/python" scripts/mock_energyua.py > "$CFG/mock.log" 2>&1 &
  echo "mock PID $! ($MOCK)"
  nohup "$VENV/hass" --config "$CFG" > "$CFG/ha.log" 2>&1 &
  echo "hass PID $! (waiting for $BASE ...)"
  _wait_ha || { echo "HA did not start"; tail -30 "$CFG/ha.log"; exit 1; }
  ACCESS=$("$VENV/python" scripts/ha_auth.py "$BASE" admin poweroff1234 | tail -1)
  [ -z "$ACCESS" ] && { echo "auth failed"; exit 1; }
  echo "$ACCESS" > "$CFG/.ha_token"
  "$VENV/python" scripts/add_entry.py "$BASE" "$ACCESS" "$GROUP"
  for _ in $(seq 1 20); do cmd_show 2>/dev/null | grep -q "sensor.power_state" && break; sleep 2; done
  echo ""; echo "✅ READY. UI: $BASE/poweroff/0  (admin / poweroff1234)"
  cmd_show
}

cmd_restart() {
  # Restart HA only (mock and .storage stay): checks that the schedule comes back from cache
  pkill -TERM -f "hass --config $CFG" 2>/dev/null || true
  for _ in $(seq 1 20); do [ -z "$(_hass_pids)" ] && break; sleep 1; done
  _wait_port_free "$PORT_HA" || true
  nohup "$VENV/hass" --config "$CFG" > "$CFG/ha.log" 2>&1 &
  echo "hass PID $! (waiting...)"
  _wait_ha || { echo "HA did not start"; tail -30 "$CFG/ha.log"; exit 1; }
  for _ in $(seq 1 20); do cmd_show 2>/dev/null | grep -q "sensor.power_state" && break; sleep 2; done
  cmd_show
}

cmd_show() {
  ACCESS=$(cat "$CFG/.ha_token")
  curl -s "$BASE/api/states" -H "Authorization: Bearer $ACCESS" | "$VENV/python" -c "
import sys, json
try: d = json.load(sys.stdin)
except Exception: print('  (HA is not ready yet)'); sys.exit()
keys = ('power', 'schedule', 'poweroff')
for x in d if isinstance(d, list) else []:
    if any(k in x['entity_id'] for k in keys):
        a = x['attributes']
        extra = f\"  stale={a.get('data_stale')} err={a.get('last_error')!r}\" if 'data_stale' in a else ''
        print(f\"  {x['entity_id']} = {x['state']}{extra}\")"
}

cmd_mode() {
  curl -s -X POST "$MOCK/_test/mode" -H 'Content-Type: application/json' -d "{\"mode\":\"$1\"}"; echo
  cmd_refresh
}

cmd_refresh() {
  ACCESS=$(cat "$CFG/.ha_token")
  curl -s -X POST "$BASE/api/services/poltava_poweroff/refresh" -H "Authorization: Bearer $ACCESS" >/dev/null
  sleep 3; cmd_show
}

cmd_shot() {
  mkdir -p screenshots
  "$VENV/python" scripts/screenshot.py "$BASE" "$(cat "$CFG/.ha_token")" "screenshots/${1:-dashboard}.png"
}

cmd_readme() {
  "$VENV/python" scripts/readme_screenshots.py "$BASE" "$(cat "$CFG/.ha_token")" "$MOCK" pics
}

cmd_down() {
  pkill -TERM -f "hass --config $CFG" 2>/dev/null || true
  pkill -TERM -f "scripts/mock_energyua.py" 2>/dev/null || true
  for _ in $(seq 1 15); do [ -z "$(_hass_pids)" ] && break; sleep 1; done
  pkill -9 -f "hass --config $CFG" 2>/dev/null || true
  pkill -9 -f "scripts/mock_energyua.py" 2>/dev/null || true
  for p in "$PORT_HA" "$PORT_MOCK"; do _pids_on "$p" | xargs kill -9 2>/dev/null || true; done
  echo "stopped"
}

case "${1:-up}" in
  up) cmd_up ;;
  mode) cmd_mode "${2:?mode: ok|nodata|http500|garbage|timeout}" ;;
  refresh) cmd_refresh ;;
  restart) cmd_restart ;;
  show) cmd_show ;;
  shot) cmd_shot "${2:-dashboard}" ;;
  readme) cmd_readme ;;
  down) cmd_down ;;
  *) echo "usage: $0 {up|mode <m>|refresh|restart|show|shot [name]|readme|down}"; exit 1 ;;
esac

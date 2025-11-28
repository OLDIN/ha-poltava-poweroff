#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${HA_LOG:-/tmp/ha.log}"
HEALTHCHECK_URL="${HA_HEALTHCHECK_URL:-http://127.0.0.1:8123/}"
RESTART_DELAY="${HA_RESTART_DELAY:-5}"
curl_opts=("--fail" "--silent" "--show-error")

echo "[ha-guard] Writing logs to ${LOG_FILE}"

shutdown() {
    echo "[ha-guard] Caught termination signal, stopping Home Assistant loop"
    exit 0
}
trap shutdown SIGINT SIGTERM

wait_for_ready() {
    local attempt=0
    local max_attempts="${HA_HEALTHCHECK_ATTEMPTS:-60}"
    while (( attempt < max_attempts )); do
        if curl "${curl_opts[@]}" "${HEALTHCHECK_URL}" >/dev/null 2>&1; then
            echo "[ha-guard] Home Assistant is up (${attempt}s)"
            return 0
        fi
        ((attempt++))
        sleep 1
    done
    echo "[ha-guard] Home Assistant failed healthcheck after ${max_attempts}s"
    return 1
}

while true; do
    echo "[ha-guard] Starting Home Assistant via scripts/develop at $(date --iso-8601=seconds)" | tee -a "${LOG_FILE}"
    if bash "${ROOT_DIR}/scripts/develop" >>"${LOG_FILE}" 2>&1; then
        echo "[ha-guard] Home Assistant exited cleanly, restarting in ${RESTART_DELAY}s"
    else
        status=$?
        echo "[ha-guard] Home Assistant crashed with status ${status}, restarting in ${RESTART_DELAY}s" | tee -a "${LOG_FILE}"
    fi

    wait_for_ready || true

    sleep "${RESTART_DELAY}"
done

#!/usr/bin/env bash
# Create .venv-ha with Home Assistant + test dependencies (once).
#   scripts/setup_dev_env.sh            — python3.13 from PATH
#   PYTHON=/opt/homebrew/bin/python3.13 scripts/setup_dev_env.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3.13}"
[ -d .venv-ha ] || "$PY" -m venv .venv-ha
.venv-ha/bin/pip install -U pip wheel
# HA + test dependencies with pinned versions (the same as in the devcontainer)
.venv-ha/bin/pip install -r requirements.txt playwright
# Check: modules the frontend queries via get_services must import
.venv-ha/bin/python -c "from homeassistant.helpers.service import _base_components; _base_components(); print('HA base components OK')"
.venv-ha/bin/python -m playwright install chromium
echo "✅ .venv-ha is ready. Next: scripts/dev_ha_ui.sh up"

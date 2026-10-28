#!/usr/bin/env bash
# Створити .venv-ha з Home Assistant + тестовими залежностями (один раз).
#   scripts/setup_dev_env.sh            — python3.13 з PATH
#   PYTHON=/opt/homebrew/bin/python3.13 scripts/setup_dev_env.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3.13}"
[ -d .venv-ha ] || "$PY" -m venv .venv-ha
.venv-ha/bin/pip install -U pip wheel
# HA + тестові залежності з закріпленими версіями (ті самі, що в devcontainer)
.venv-ha/bin/pip install -r requirements.txt playwright
# Перевірка: модулі, які фронтенд опитує через get_services, мають імпортуватись
.venv-ha/bin/python -c "from homeassistant.helpers.service import _base_components; _base_components(); print('HA base components OK')"
.venv-ha/bin/python -m playwright install chromium
echo "✅ .venv-ha готовий. Далі: scripts/dev_ha_ui.sh up"

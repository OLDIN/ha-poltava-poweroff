#!/usr/bin/env bash
# Створити .venv-ha з Home Assistant + тестовими залежностями (один раз).
#   scripts/setup_dev_env.sh            — python3.13 з PATH
#   PYTHON=/opt/homebrew/bin/python3.13 scripts/setup_dev_env.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3.13}"
[ -d .venv-ha ] || "$PY" -m venv .venv-ha
.venv-ha/bin/pip install -U pip wheel
# pytest-homeassistant-custom-component тягне сумісну версію homeassistant
.venv-ha/bin/pip install pytest-homeassistant-custom-component beautifulsoup4 cloudscraper brotli playwright
# Пакети, без яких фронтенд HA зависає на "Loading data" (get_services падає) — точні версії з constraints ядра
HA_DIR=$(.venv-ha/bin/python -c 'import homeassistant, os; print(os.path.dirname(homeassistant.__file__))')
.venv-ha/bin/pip install $(grep -iE '^(hassil|home-assistant-intents|ha-ffmpeg|mutagen|PyTurboJPEG|pymicro-vad|pyspeex-noise)==' "$HA_DIR/package_constraints.txt")
# Перевірка: модулі, які фронтенд опитує через get_services, мають імпортуватись
.venv-ha/bin/python -c "from homeassistant.helpers.service import _base_components; _base_components(); print('HA base components OK')"
.venv-ha/bin/python -m playwright install chromium
echo "✅ .venv-ha готовий. Далі: scripts/dev_ha_ui.sh up"

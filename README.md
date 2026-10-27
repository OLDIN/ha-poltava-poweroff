[![SWUbanner](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua/)

![HA Poltava PowerOff Logo](https://raw.githubusercontent.com/OLDIN/ha-poltava-poweroff/main/custom_components/poltava_poweroff/icon.png)

# ⚡️ Home Assistant Poltava PowerOff

An integration for electricity shutdown schedules of [PoltavaOblEnergo](poltavaoblenergo). Based on data from [EnergyUA][energyua].

This integration for [Home Assistant][home-assistant] provides information about planned electricity shutdowns of [PoltavaOblEnergo](poltavaoblenergo) in Poltava oblast:
calendar of planned shutdowns, time sensors for the next planned power on and off events. It is based on messages posted by a community
driven project [EnergyUA][energyua].

**💡 Note:** This project is not affiliated with [EnergyUA][energyua] or [PoltavaOblEnergo](poltavaoblenergo) in any way. This integration is developed by an individual.
Provided data may be incorrect or misleading, follow the official channels for reliable information.

> This integration is inspired by [ha-yasno-outages](https://github.com/denysdovhan/ha-yasno-outages) by [Denys Dovhan](https://github.com/denysdovhan).

## Installation

The quickest way to install this integration is via [HACS][hacs-url] by clicking the button below:

[![Add to HACS via My Home Assistant][hacs-install-image]][hasc-install-url]

If it doesn't work, adding this repository to HACS manually by adding this URL:

1. Visit **HACS** → **Integrations** → **...** (in the top right) → **Custom repositories**
1. Click **Add**
1. Paste `https://github.com/OLDIN/ha-poltava-poweroff` into the **URL** field
1. Chose **Integration** as a **Category**
1. **Poltava PowerOff** will appear in the list of available integrations. Install it normally.

## Usage

This integration is configurable via UI. On **Devices and Services** page, click **Add Integration** and search for **Poltava PowerOff**.

Find your group by visiting [EnergyUA][energyua] website and typing your address in the search bar. Select your group in the configuration.

Then you can add the integration to your dashboard and see the information about the next planned outages.

![Sensors](https://github.com/OLDIN/ha-poltava-poweroff/blob/827c15582bb64c70568f6f7b322e926feeaa2592/pics/example_sensor.png?raw=true)

### Manual Data Refresh

The integration automatically updates data every **5 minutes**. If you need to force an immediate update (e.g., when the schedule changes on the website), you can use the service:

**Via Developer Tools:**
1. Go to **Settings → Developer Tools → Services**
2. Select `poltava_poweroff.refresh` from the service dropdown
3. Click **Call Service**

**Via YAML (automation/script):**
```yaml
service: poltava_poweroff.refresh
```

### Viewing other queues (queue switcher)

The card has a queue chip in its header (🏠 marks your queue). Pick any of 1.1…6.2 to see that queue's schedule; a blue banner reminds you that you're viewing someone else's queue and offers **Повернутись**.

- The choice is stored in `select.poweroff_view_queue` and survives restarts. It is shared by everyone in the household.
- Sensors, the calendar and your automations **always** follow the queue you configured — the switcher only changes what the card shows.
- Only your queue and the last selected one are polled in the background; another queue is fetched the moment you select it (cached for 5 minutes, and kept on disk like your own).
- The card finds the select automatically. To pin it explicitly use `queue_entity: select.poweroff_view_queue`, or hide the switcher with `queue_entity: false`.

Hover (or tap on a phone) the "Графік оновлено …" line: a tooltip shows when data was last fetched from the site successfully (even if the schedule did not change), the last attempt and the error, if any.

### When energy-ua.info is down

The schedule is cached on disk (`.storage/poltava_poweroff.<entry_id>`) by **date**, so:

- if the site is unreachable, returns an error page, a Cloudflare challenge or "Немає даних", the last good schedule stays visible — sensors do **not** go empty or `unavailable`;
- after a Home Assistant restart the schedule is restored from cache even if the site is still down;
- at midnight tomorrow's schedule becomes today's automatically, without contacting the site.

The card shows an orange banner when it is displaying a cached schedule, and a "Графік оновлено …" line with the time the schedule last **changed**.

| Entity / attribute | Meaning |
|---|---|
| `sensor.schedule_updated` | When the schedule on the site last changed (not just re-fetched) |
| `sensor.schedule_last_fetch` (diagnostic) | Last successful request to the site |
| `sensor.power_state` → `data_stale` | `true` while the last request failed and cached data is shown |
| `sensor.power_state` → `last_error` | Why the last request failed |
| `sensor.power_state` → `today_known` / `tomorrow_known` | Whether the site has published a schedule for that day |
| `sensor.power_state` → `queue` | Your queue as shown on the site, e.g. `4.1` |

Example — notify when the site has been unreachable for over an hour:

```yaml
trigger:
  - platform: template
    value_template: >
      {{ state_attr('sensor.power_state', 'data_stale')
         and (now() - states('sensor.schedule_last_fetch') | as_datetime) > timedelta(hours=1) }}
```

Integration also provides a calendar view of planned outages. You can add it to your dashboard as well via [Calendar card][calendar-card].

![Calendar](https://github.com/OLDIN/ha-poltava-poweroff/blob/827c15582bb64c70568f6f7b322e926feeaa2592/pics/example_calendar.png?raw=true)

### Lovelace “Snail” (Poweroff Timeline Card)

Starting from the bundled `poweroff-timeline-card.js`, the Lovelace resource is registered automatically, so Home Assistant OS / Supervised requires no extra tweaks:

1. Go to **Settings → Devices & Services**, add **Poltava PowerOff**, and select your queue.
2. Click the badge below (or copy the link) to open Home Assistant’s card editor with a pre-filled configuration. The only thing you’ll need to adjust is the entity ID if it differs from `sensor.power_state`.

[![Add Lovelace Card via My Home Assistant](https://my.home-assistant.io/badges/lovelace_card.svg)](https://my.home-assistant.io/redirect/lovelace_card/?config=%7B%22type%22%3A%22custom%3Apoweroff-timeline-card%22%2C%22entity%22%3A%22sensor.power_state%22%2C%22title%22%3A%22Outages%20Today%22%7D)

3. Alternatively, open your Lovelace dashboard and choose **Edit → Add card → Custom: Power Off Timeline Card** (if the GUI does not list custom cards, click **Manual** and paste the snippet below):

```yaml
type: custom:poweroff-timeline-card
entity: sensor.power_state  # replace with your sensor.<id>
title: Outages Today
```

4. Reload the dashboard (hard refresh if needed) and the spiral card will appear. Inside the devcontainer ensure the guard script has already started Home Assistant, otherwise Lovelace cannot load `/local/poltava_poweroff/poweroff-timeline-card.js`.

> The resource lives in `custom_components/poltava_poweroff/www`. If you run bare Core without Supervisor, add `/local/poltava_poweroff/poweroff-timeline-card.js` under **Settings → Dashboards → Resources** manually.

## Dev Container workflow

For local development we ship a ready-to-go [VS Code Dev Container](.devcontainer.json):

1. Install the Dev Containers extension and run **Dev Containers: Reopen in Container**. The image is built from the repo `Dockerfile`, applying the `git` and `docker-outside-of-docker` features so you can commit and use Docker inside the workspace.
2. The container expects at least 4 CPUs, 8 GB RAM and 20 GB of disk (see `hostRequirements`). Codespaces or local Docker Desktop should prompt you if the host is undersized.
3. During `postCreateCommand` the helper script `scripts/setup` installs Python tooling and hooks. When the container starts, `scripts/devcontainer_ha_guard.sh` launches Home Assistant via `scripts/develop`, keeps it running, and tails output into `/tmp/ha.log`. The guard’s own status messages end up in `/tmp/ha-guard.log` (tail it when diagnosing autostart issues).
4. Forwarded port 8123 is labeled “Home Assistant”. Once logs show `Home Assistant is up`, visit `http://localhost:8123/` (or the forwarded URL in Codespaces) to test the custom card/integration. Restarting the server is as easy as `docker restart <container>` or stopping the guard script.
5. Use environment variables `HA_LOG`, `HA_HEALTHCHECK_URL`, `HA_HEALTHCHECK_ATTEMPTS`, or `HA_RESTART_DELAY` to tweak the guard behaviour when needed.

## Development

### Running Tests

To run tests, first install the dependencies:

```bash
# Install all dependencies (including Home Assistant)
pip install -r requirements.txt

# Or only test dependencies (if Home Assistant is already installed)
pip install pytest pytest-asyncio aioresponses beautifulsoup4 cloudscraper voluptuous
```

After that, you can run the tests:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_energyua_scrapper.py

# Run a specific test case
pytest tests/test_energyua_scrapper.py::test_energyua_scrapper -v

# Run with code coverage (if pytest-cov is installed)
pytest --cov=custom_components/poltava_poweroff --cov-report=html
```

**Notes:**
- The pytest configuration is in `pytest.ini` and automatically adds `custom_components` to PYTHONPATH for correct imports
- Tests require Home Assistant for correct module imports
- If you use anaconda/miniconda, make sure to install dependencies in the correct environment

### Local Home Assistant with a mock energy-ua (UI + screenshots)

Same approach as in `ha-silpo`: a real Home Assistant process with the integration symlinked in, talking to a local mock of energy-ua.info that you can "break" on demand.

```bash
scripts/setup_dev_env.sh          # once: creates .venv-ha (HA + test deps + Playwright Chromium)
scripts/dev_ha_ui.sh up           # HA on http://127.0.0.1:8124/poweroff/0  (admin / poweroff1234)
scripts/dev_ha_ui.sh mode http500 # site down → card shows cached schedule + banner
scripts/dev_ha_ui.sh mode garbage # Cloudflare / maintenance page
scripts/dev_ha_ui.sh mode nodata  # "Немає даних" — known days are kept
scripts/dev_ha_ui.sh mode ok
scripts/dev_ha_ui.sh restart      # restart HA only — schedule must come back from cache
scripts/dev_ha_ui.sh shot site_down   # screenshots/site_down.png (full dashboard)
scripts/dev_ha_ui.sh down
```

The mock (`scripts/mock_energyua.py`) renders pages in the site's HTML format. Change the schedule with
`curl -X POST 127.0.0.1:8798/_test/schedule -d '{"today": [[8, 9.5]], "tomorrow": null}'`.
The integration reads its base URL from `POLTAVA_POWEROFF_BASE_URL` (defaults to `https://energy-ua.info`).
Runtime files (`ha_config/`, `.venv-ha/`, `screenshots/`) are git-ignored.

### Running JavaScript Tests

The project includes tests for the Lovelace card UI component. To run JavaScript tests:

```bash
# Install Node.js dependencies (first time only)
npm install

# Run all JavaScript tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with UI
npm run test:ui
```

**JavaScript Test Coverage:**
- Component initialization and configuration
- UI rendering (spiral chart, legend, buttons)
- Tab switching (today/tomorrow)
- Pattern building for power off periods
- Time formatting
- Edge cases (missing entities, empty periods)
- **Image snapshots** - Visual regression testing with PNG images

**Image Snapshots:**
The tests render the card in headless Chromium (Puppeteer) and compare it with reference PNGs in `tests/js/__snapshots__/`. The card ships its own font (Inter, `www/fonts/`), so the pictures are the same on macOS, Linux and CI — one set of references for everyone. The clock is frozen during these tests and tiny rendering differences are tolerated. On a mismatch the test writes `*-actual-diff.png` and `*-diff.png` next to the reference (git-ignored). If Chromium cannot start, the snapshot tests are skipped.

To update snapshots after intentional UI changes:
```bash
rm tests/js/__snapshots__/*.png
npm test
```

### Version Management

For developers, use the automated version bump script for easy releases:

```bash
# Quick automated release (recommended for maintainers)
python scripts/bump_version.py patch --push --notes

# Semi-automated (commit & tag, manual push)
python scripts/bump_version.py patch --commit

# Manual workflow (traditional)
python scripts/bump_version.py patch
git add custom_components/poltava_poweroff/manifest.json
git commit -m "Bump version to X.Y.Z"
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin main --tags
```

**Options:**
- `-c, --commit`: Automatically commit changes and create git tag
- `-p, --push`: Push commits and tags to GitHub (implies `--commit`)
- `-n, --notes`: Generate release notes from commit messages

See [docs/VERSION_MANAGEMENT.md](docs/VERSION_MANAGEMENT.md) for detailed documentation.

## Versioning and Updates

This integration uses [semantic versioning](https://semver.org/) (MAJOR.MINOR.PATCH). The version is stored in `custom_components/poltava_poweroff/manifest.json`.

### For Users

**HACS automatically detects updates** when:
- A new version is released (version in `manifest.json` changes)
- You have the integration installed via HACS

#### Method 1: Update via HACS (Recommended)

1. Go to **HACS** → **Integrations**
2. Find **Poltava PowerOff** in the list
3. If an update is available, you'll see an **Update** button (or a version badge showing available update)
4. Click **Update** button
5. Wait for the update to complete
6. **Restart Home Assistant** (Settings → System → Restart)

#### Method 2: Manual Update via File System

If you installed the integration manually (not via HACS):

1. **SSH into your Home Assistant OS** or use the **Terminal** add-on
2. Navigate to the custom components directory:
   ```bash
   cd /config/custom_components/poltava_poweroff
   ```
3. Pull the latest changes:
   ```bash
   git pull origin main
   ```
   Or if you need to update to a specific version:
   ```bash
   git fetch --tags
   git checkout v0.1.0  # Replace with the version you want
   ```
4. **Restart Home Assistant** (Settings → System → Restart)

#### Method 3: Reinstall via HACS

If the update doesn't appear or you have issues:

1. Go to **HACS** → **Integrations**
2. Find **Poltava PowerOff**
3. Click the **...** (three dots) menu → **Redownload**
4. **Restart Home Assistant**

**Note:** After updating, check the integration version in **Settings → Devices & Services → Poltava PowerOff** → **...** → **System options** to verify the update was successful.

### For Developers

To bump the version when making changes:

```bash
# Patch version (bug fixes): 0.1.0 -> 0.1.1
python scripts/bump_version.py patch

# Minor version (new features): 0.1.0 -> 0.2.0
python scripts/bump_version.py minor

# Major version (breaking changes): 0.1.0 -> 1.0.0
python scripts/bump_version.py major
```

The script will:
1. Update `manifest.json` with the new version
2. Show you the git commands to commit and tag the release

**Release workflow:**

**Minimum required (HACS will detect updates):**
1. Make your changes
2. Bump version: `python scripts/bump_version.py patch|minor|major`
3. Commit and push: `git commit -am "Bump version to X.Y.Z" && git push origin main`

**Recommended (with git tags for better tracking):**
1. Make your changes
2. Bump version: `python scripts/bump_version.py patch|minor|major`
3. Commit changes: `git commit -am "Description of changes"`
4. Tag release: `git tag -a v0.1.1 -m "Release 0.1.1"`
5. Push: `git push origin main --tags`

**How HACS detects updates:**
- HACS periodically checks the repository (every 4-6 hours) and reads `manifest.json`
- It compares the version in the repo with the installed version
- If the repo version is higher, it shows an update notification
- Users can also manually trigger a check in HACS → Integrations → "Check for updates"

**Note:**
- **Git tags are NOT required** for HACS to detect updates. HACS reads `manifest.json` from the main branch.
- Git tags and GitHub releases are **optional** but useful for:
  - Better version tracking in git history
  - GitHub releases with changelog/notes
  - Ability to checkout specific versions
  - Professional project organization

<!-- References -->

[energyua]: https://energy-ua.info/
[poltavaoblenergo]: https://www.poe.pl.ua/
[home-assistant]: https://www.home-assistant.io/
[hacs-url]: https://github.com/hacs/integration
[hasc-install-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=OLDIN&repository=ha-poltava-poweroff&category=integration
[hacs-install-image]: https://my.home-assistant.io/badges/hacs_repository.svg
[calendar-card]: https://www.home-assistant.io/dashboards/calendar/

ha-yasno-outages

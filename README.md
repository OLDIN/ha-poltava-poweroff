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

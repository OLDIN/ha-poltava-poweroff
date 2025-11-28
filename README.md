[![SWUbanner](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua/)

![HA Poltava PowerOff Logo](https://github.com/tsdaemon/ha-lviv-poweroff/blob/827c15582bb64c70568f6f7b322e926feeaa2592/icons/icon.png?raw=true)

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

Integration also provides a calendar view of planned outages. You can add it to your dashboard as well via [Calendar card][calendar-card].

![Calendar](https://github.com/OLDIN/ha-poltava-poweroff/blob/827c15582bb64c70568f6f7b322e926feeaa2592/pics/example_calendar.png?raw=true)

## Dev Container workflow

For local development we ship a ready-to-go [VS Code Dev Container](.devcontainer.json):

1. Install the Dev Containers extension and run **Dev Containers: Reopen in Container**. The image is built from the repo `Dockerfile`, applying the `git` and `docker-outside-of-docker` features so you can commit and use Docker inside the workspace.
2. The container expects at least 4 CPUs, 8 GB RAM and 20 GB of disk (see `hostRequirements`). Codespaces or local Docker Desktop should prompt you if the host is undersized.
3. During `postCreateCommand` the helper script `scripts/setup` installs Python tooling and hooks. When the container starts, `scripts/devcontainer_ha_guard.sh` launches Home Assistant via `scripts/develop`, keeps it running, and tails output into `/tmp/ha.log`. The guard’s own status messages end up in `/tmp/ha-guard.log` (tail it when diagnosing autostart issues).
4. Forwarded port 8123 is labeled “Home Assistant”. Once logs show `Home Assistant is up`, visit `http://localhost:8123/` (or the forwarded URL in Codespaces) to test the custom card/integration. Restarting the server is as easy as `docker restart <container>` or stopping the guard script.
5. Use environment variables `HA_LOG`, `HA_HEALTHCHECK_URL`, `HA_HEALTHCHECK_ATTEMPTS`, or `HA_RESTART_DELAY` to tweak the guard behaviour when needed.

<!-- References -->

[energyua]: https://energy-ua.info/
[poltavaoblenergo]: https://www.poe.pl.ua/
[home-assistant]: https://www.home-assistant.io/
[hacs-url]: https://github.com/hacs/integration
[hasc-install-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=OLDIN&repository=ha-poltava-poweroff&category=integration
[hacs-install-image]: https://my.home-assistant.io/badges/hacs_repository.svg
[calendar-card]: https://www.home-assistant.io/dashboards/calendar/

ha-yasno-outages

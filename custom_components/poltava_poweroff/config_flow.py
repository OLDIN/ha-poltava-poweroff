"""Config flow for Poltava Power Offline: pick a schedule source, then a queue.

The same two steps are used to add an entry and to reconfigure one later
(Settings → Devices & Services → the entry → ⋮ → Reconfigure).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .const import CONF_SOURCE, DOMAIN, POWEROFF_GROUP_CONF, group_display
from .sources import DEFAULT_SOURCE, SOURCES, get_source

_LOGGER = logging.getLogger(__name__)


def unique_id_for(source_id: str, queue: str) -> str:
    """One entry per source and queue: the same queue number means different things in different regions."""
    return f"{source_id}:{queue}"


def _source_schema(default: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SOURCE, default=default): SelectSelector(
                SelectSelectorConfig(
                    options=list(SOURCES),
                    translation_key="source",  # names come from strings.json → selector.source.options
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


def _queue_schema(source_id: str, default: str | None) -> vol.Schema:
    # Dropdown "1.1 … 6.2"; the stored value keeps the "1-1" form
    queues = {q: group_display(q) for q in get_source(source_id).queues}
    key = vol.Required(POWEROFF_GROUP_CONF, default=default) if default in queues else vol.Required(POWEROFF_GROUP_CONF)
    return vol.Schema({key: vol.In(queues)})


async def _move_entities_to_queue(hass, entry_id: str, old_queue: str, new_queue: str) -> None:
    """Sensor and calendar unique ids contain the queue: rename them so the same entities
    (entity ids, history, automations) follow the new queue instead of new "_2" entities appearing."""
    old, new = f"{entry_id}-{old_queue}-", f"{entry_id}-{new_queue}-"

    @callback
    def migrate(entity: er.RegistryEntry) -> dict[str, str] | None:
        if entity.unique_id.startswith(old):
            return {"new_unique_id": new + entity.unique_id[len(old) :]}
        return None

    await er.async_migrate_entries(hass, entry_id, migrate)


class PoltavaPowerOffConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Poltava Power Offline."""

    VERSION = 2  # 2: the schedule source is stored in the entry (see async_migrate_entry)

    def __init__(self) -> None:
        self._source_id: str = DEFAULT_SOURCE

    # ----------------------------------------------------------------- add

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: where the schedule comes from."""
        if user_input is not None:
            self._source_id = user_input[CONF_SOURCE]
            return await self.async_step_queue()
        return self.async_show_form(step_id="user", data_schema=_source_schema(DEFAULT_SOURCE))

    async def async_step_queue(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 2: which queue, among the queues of the chosen source."""
        errors: dict[str, str] = {}
        if user_input is not None:
            queue = user_input[POWEROFF_GROUP_CONF]
            await self.async_set_unique_id(unique_id_for(self._source_id, queue))
            self._abort_if_unique_id_configured()
            errors = await self._validate(queue)
            if not errors:
                return self.async_create_entry(
                    title=self._title(queue), data={CONF_SOURCE: self._source_id, POWEROFF_GROUP_CONF: queue}
                )
        return self.async_show_form(
            step_id="queue",
            data_schema=_queue_schema(self._source_id, None),
            errors=errors,
        )

    # ----------------------------------------------------------- reconfigure

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the source (and queue) of an existing entry; its entities and history stay."""
        entry = self._get_reconfigure_entry()
        current = entry.data.get(CONF_SOURCE, DEFAULT_SOURCE)
        if user_input is not None:
            self._source_id = user_input[CONF_SOURCE]
            return await self.async_step_reconfigure_queue()
        return self.async_show_form(step_id="reconfigure", data_schema=_source_schema(current))

    async def async_step_reconfigure_queue(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            queue = user_input[POWEROFF_GROUP_CONF]
            unique_id = unique_id_for(self._source_id, queue)
            await self.async_set_unique_id(unique_id)
            if unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()
            errors = await self._validate(queue)
            if not errors:
                old_queue = entry.data.get(POWEROFF_GROUP_CONF)
                if old_queue != queue:
                    await _move_entities_to_queue(self.hass, entry.entry_id, str(old_queue), queue)
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=unique_id,
                    title=self._title(queue),
                    data={**entry.data, CONF_SOURCE: self._source_id, POWEROFF_GROUP_CONF: queue},
                )
        return self.async_show_form(
            step_id="reconfigure_queue",
            data_schema=_queue_schema(self._source_id, entry.data.get(POWEROFF_GROUP_CONF)),
            errors=errors,
        )

    # --------------------------------------------------------------- helpers

    def _title(self, queue: str) -> str:
        return f"{get_source(self._source_id).title} {group_display(queue)}"

    async def _validate(self, queue: str) -> dict[str, str]:
        try:
            if not await get_source(self._source_id).create(queue).validate():
                return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        return {}

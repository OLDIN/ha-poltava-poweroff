"""Registry of schedule sources the user can pick in the integration settings.

To add a source (another region, another site), see "Adding a schedule source" in the README:
write a provider (see base.py), then register it here with an id, its queues and a factory,
and add its name to the "source" selector in strings.json and translations/*.json.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .base import FallbackProvider, ScheduleProvider
from .energy_ua import EnergyUaScrapper
from .poe import PoeScrapper

# The 12 sub-queues used by Ukrainian distribution companies, stored in the "1-1" form
UA_QUEUES: tuple[str, ...] = tuple(f"{a}-{b}" for a in range(1, 7) for b in (1, 2))


@dataclass(frozen=True)
class SourceInfo:
    """A selectable source."""

    id: str  # stored in the config entry; never change it once released
    title: str  # config entry title prefix, e.g. "Poltava Power Offline 4.1"
    queues: tuple[str, ...]  # queue ids, "1-1" … (shown as "1.1")
    factory: Callable[[str], ScheduleProvider]  # queue -> provider

    def create(self, queue: str) -> ScheduleProvider:
        return self.factory(queue)


SOURCES: dict[str, SourceInfo] = {
    source.id: source
    for source in (
        SourceInfo(
            id="poltava",
            title="Poltava Power Offline",
            queues=UA_QUEUES,
            factory=lambda queue: FallbackProvider([PoeScrapper(queue), EnergyUaScrapper(queue)]),
        ),
        SourceInfo(id="poltava_poe", title="Poltava (poe.pl.ua)", queues=UA_QUEUES, factory=PoeScrapper),
        SourceInfo(
            id="poltava_energy_ua", title="Poltava (energy-ua.info)", queues=UA_QUEUES, factory=EnergyUaScrapper
        ),
    )
}

# Entries created before sources were selectable (config entry version 1) use this one
DEFAULT_SOURCE = "poltava"


def get_source(source_id: str | None) -> SourceInfo:
    """The source of a config entry; unknown ids (a removed source) fall back to the default."""
    return SOURCES.get(source_id or DEFAULT_SOURCE) or SOURCES[DEFAULT_SOURCE]

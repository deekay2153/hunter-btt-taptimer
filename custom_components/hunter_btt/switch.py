from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BttEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities([BttOutletSwitch(c, "outlet", n) for n in c.outlets])


class BttOutletSwitch(BttEntity, SwitchEntity):
    """On = water from this outlet for its run-time setting. Off = stop this outlet."""

    _attr_icon = "mdi:water-pump"

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_running(self.outlet)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_start(self.outlet)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_stop(self.outlet)

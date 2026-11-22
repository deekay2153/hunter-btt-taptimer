from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .codec import MAX_RUN_MINUTES
from .const import DEFAULT_RUN_MINUTES
from .entity import BttEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities([BttRunTime(c, "run_time", n) for n in c.outlets])


class BttRunTime(BttEntity, RestoreNumber):
    """How long the outlet switch waters for. Kept in HA; sent to the timer with each start."""

    _attr_native_min_value = 1
    _attr_native_max_value = MAX_RUN_MINUTES
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-outline"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        value = int(last.native_value) if last and last.native_value is not None else DEFAULT_RUN_MINUTES
        self.coordinator.run_minutes[self.outlet] = min(max(value, 1), MAX_RUN_MINUTES)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.run_minutes[self.outlet]

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.run_minutes[self.outlet] = int(value)
        self.async_write_ha_state()

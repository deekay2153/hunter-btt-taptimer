from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BttEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            *(BttRemaining(c, "time_remaining", n) for n in c.outlets),
            BttBattery(c, "battery"),
            BttRawStatus(c, "raw_status"),
        ]
    )


class BttRemaining(BttEntity, SensorEntity):
    """Counted down in HA for runs started from HA. The timer doesn't report time left."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:timer-sand"

    @property
    def native_value(self) -> int:
        return self.coordinator.remaining(self.outlet)


class BttBattery(BttEntity, SensorEntity):
    """Battery %, read on idle polls (every 30 min)."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int | None:
        return self.coordinator.battery


class BttRawStatus(BttEntity, SensorEntity):
    """The timer's 14 status bytes in hex, so early users can report what their timer sends."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:code-brackets"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.raw.hex(" ") if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data
        if not d:
            return {}
        attrs = {"firmware": self.coordinator.firmware, "enabled": d.enabled, "suspend": d.suspend}
        for n in self.coordinator.outlets:
            o = d.outlets[n]
            attrs[f"outlet_{n}_state"] = o.state
            attrs[f"outlet_{n}_manual"] = o.manual
            attrs[f"outlet_{n}_mode"] = o.mode
        return attrs

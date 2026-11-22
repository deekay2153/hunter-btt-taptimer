from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BttCoordinator


class BttEntity(CoordinatorEntity[BttCoordinator]):
    """Timer-wide entities pass outlet=None; outlet entities pass 1 or 2."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BttCoordinator, key: str, outlet: int | None = None) -> None:
        super().__init__(coordinator)
        address = coordinator.timer.address
        self.outlet = outlet
        suffix = "" if outlet is None else f"_{outlet}"
        self._attr_unique_id = f"{address}_{key}{suffix}"
        self._attr_translation_key = key
        if outlet is not None:
            self._attr_translation_placeholders = {"outlet": str(outlet)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
            name=coordinator.timer.name,
            manufacturer="Hunter Industries",
            model="BTT tap timer",
            sw_version=coordinator.firmware,
        )

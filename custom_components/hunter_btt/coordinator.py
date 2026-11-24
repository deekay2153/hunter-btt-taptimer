from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import codec
from .const import CONF_OUTLETS, DEFAULT_RUN_MINUTES, IDLE_INTERVAL, RUNNING_INTERVAL
from .protocol import BttError, HunterBtt

_LOGGER = logging.getLogger(__name__)


class BttCoordinator(DataUpdateCoordinator[codec.Status]):
    """data = the timer's live status (0xFF82)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, timer: HunterBtt) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=timer.name, update_interval=IDLE_INTERVAL)
        self.timer = timer
        self.outlets = list(range(1, entry.data.get(CONF_OUTLETS, 1) + 1))
        self.run_minutes = {n: DEFAULT_RUN_MINUTES for n in self.outlets}
        self.ends_at: dict[int, datetime | None] = {n: None for n in self.outlets}  # only for runs started here
        self.battery: int | None = None
        self.firmware: str | None = None

    def is_running(self, outlet: int) -> bool:
        o = self.data.outlets.get(outlet) if self.data else None
        return bool(o and o.running)

    def remaining(self, outlet: int) -> int:
        end = self.ends_at.get(outlet)
        if not self.is_running(outlet) or end is None:
            return 0
        return max(0, int((end - dt_util.utcnow()).total_seconds()))

    def _apply(self, status: codec.Status) -> codec.Status:
        # Older timers have one outlet, whatever was picked at setup.
        self.outlets = [n for n in self.outlets if n in status.outlets] or [1]
        for n in self.outlets:
            if not status.outlets[n].running:
                self.ends_at[n] = None
        running = any(status.outlets[n].running for n in self.outlets)
        self.update_interval = RUNNING_INTERVAL if running else IDLE_INTERVAL
        return status

    async def _async_update_data(self) -> codec.Status:
        full = not any(self.is_running(n) for n in self.outlets)
        try:
            reply = await self.timer.poll(full)
        except (BttError, codec.CodecError) as err:
            raise UpdateFailed(str(err)) from err
        if full:
            self.battery = reply.get("battery")
            self.firmware = reply.get("firmware")
        return self._apply(reply["status"])

    async def async_start(self, outlet: int, minutes: int | None = None) -> None:
        minutes = int(minutes or self.run_minutes[outlet])
        try:
            status = await self.timer.start(outlet, minutes)
        except (BttError, codec.CodecError) as err:
            raise HomeAssistantError(f"{self.timer.name}: {err}") from err
        # The app turns the other outlet's manual run off when starting one; so do we.
        self.ends_at = {n: None for n in self.outlets}
        self.ends_at[outlet] = dt_util.utcnow() + timedelta(minutes=minutes)
        self.async_set_updated_data(self._apply(status))
        if not status.outlets[outlet].running:
            _LOGGER.warning(
                "%s: start sent but status still shows outlet %s idle (raw %s). Please report this.",
                self.timer.name,
                outlet,
                status.raw.hex(" "),
            )

    async def async_stop(self, outlet: int) -> None:
        try:
            status = await self.timer.stop(outlet)
        except (BttError, codec.CodecError) as err:
            raise HomeAssistantError(f"{self.timer.name}: {err}") from err
        self.async_set_updated_data(self._apply(status))

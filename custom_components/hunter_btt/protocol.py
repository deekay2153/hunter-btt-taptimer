"""Hunter BTT tap timer over Home Assistant Bluetooth (local adapter or ESPHome proxy).

One connect-work-disconnect session at a time. Only the characteristics in codec.ALLOWED_READS and
codec.ALLOWED_WRITES are ever touched; firmware update (TI OAD), debug, passcode, schedules,
names and photos are never written.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import codec

_LOGGER = logging.getLogger(__name__)
SESSION_TIMEOUT = 60
T = TypeVar("T")


class BttError(Exception):
    """Session failed."""


class _Guarded:
    """The client with every read and write checked against the allow lists."""

    def __init__(self, client: BleakClient, name: str) -> None:
        self._client = client
        self._name = name

    def has(self, uuid: str) -> bool:
        return self._client.services.get_characteristic(uuid) is not None

    async def read(self, uuid: str) -> bytes:
        if uuid not in codec.ALLOWED_READS:
            raise BttError(f"read of {uuid} not allowed")
        data = bytes(await self._client.read_gatt_char(uuid))
        _LOGGER.debug("%s: read %s = %s", self._name, uuid[4:8], data.hex(" "))
        return data

    async def read_optional(self, uuid: str) -> bytes | None:
        return await self.read(uuid) if self.has(uuid) else None

    async def write(self, uuid: str, data: bytes) -> None:
        if uuid not in codec.ALLOWED_WRITES:
            raise BttError(f"write to {uuid} not allowed")
        _LOGGER.debug("%s: write %s = %s", self._name, uuid[4:8], data.hex(" "))
        await self._client.write_gatt_char(uuid, data, response=True)


class HunterBtt:
    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self._lock = asyncio.Lock()

    async def _session(self, work: Callable[[_Guarded], Awaitable[T]]) -> T:
        async with self._lock:
            device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
            if device is None:
                raise BttError(f"{self.name} ({self.address}) is not in range of a Bluetooth adapter or proxy")
            try:
                return await asyncio.wait_for(self._run(device, work), SESSION_TIMEOUT)
            except (BttError, codec.CodecError):
                raise
            except Exception as err:  # noqa: BLE001 - bleak/proxy errors vary
                raise BttError(f"{type(err).__name__}: {err}") from err

    async def _run(self, device, work: Callable[[_Guarded], Awaitable[T]]) -> T:
        client = await establish_connection(BleakClient, device, self.name, max_attempts=3)
        try:
            g = _Guarded(client, self.name)
            if client.services.get_service(codec.SERVICE) is None:
                if client.services.get_service(codec.OLD_SERVICE) is not None:
                    raise BttError("this is an older BTT (service FCC0); only newer timers (FF80) are supported")
                raise BttError("Hunter BTT service FF80 not found: is this the right device?")
            return await work(g)
        finally:
            await client.disconnect()

    async def poll(self, full: bool) -> dict[str, Any]:
        """Status every time; battery and firmware too when full."""

        async def work(g: _Guarded) -> dict[str, Any]:
            out: dict[str, Any] = {"status": codec.parse_status(await g.read(codec.STATUS))}
            if full:
                bat = await g.read_optional(codec.BATTERY)
                fw = await g.read_optional(codec.FIRMWARE)
                out["battery"] = bat[0] if bat else None
                out["firmware"] = fw.decode("utf-8", "replace").strip("\x00 ") if fw else None
            return out

        return await self._session(work)

    async def start(self, outlet: int, minutes: int) -> codec.Status:
        async def work(g: _Guarded) -> codec.Status:
            settings_uuid = codec.OUTLET_SETTINGS[outlet]
            await g.write(settings_uuid, codec.set_manual_time(await g.read(settings_uuid), minutes))
            await g.write(codec.CONTROL, codec.control_start(await g.read(codec.CONTROL), outlet))
            await asyncio.sleep(1)
            return codec.parse_status(await g.read(codec.STATUS))

        return await self._session(work)

    async def stop(self, outlet: int) -> codec.Status:
        async def work(g: _Guarded) -> codec.Status:
            await g.write(codec.CONTROL, codec.control_stop(await g.read(codec.CONTROL), outlet))
            await asyncio.sleep(1)
            return codec.parse_status(await g.read(codec.STATUS))

        return await self._session(work)

    async def snapshot(self) -> dict[str, str | None]:
        """Raw hex of every readable characteristic, for diagnostics. Never the passcode."""

        async def work(g: _Guarded) -> dict[str, str | None]:
            out: dict[str, str | None] = {}
            for uuid in sorted(codec.ALLOWED_READS):
                data = await g.read_optional(uuid)
                out[uuid[4:8].upper()] = data.hex(" ") if data is not None else None
            return out

        return await self._session(work)

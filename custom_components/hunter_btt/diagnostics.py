"""Download diagnostics: a fresh read of every characteristic this integration knows, as hex.

Lets owners confirm or correct the byte layouts. The passcode (0xFF81) is never read.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import codec
from .protocol import BttError


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    try:
        snapshot: Any = await c.timer.snapshot()
    except (BttError, codec.CodecError) as err:
        snapshot = f"read failed: {err}"
    return {
        "outlets": c.outlets,
        "firmware": c.firmware,
        "outlets_from_firmware": codec.outlets_from_firmware(c.firmware),
        "battery": c.battery,
        "last_status": c.data.raw.hex(" ") if c.data else None,
        "characteristics": snapshot,
    }

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback

from . import codec
from .const import CONF_OUTLETS, DOMAIN

OUTLET_CHOICES = {"1": "One outlet", "2": "Two outlets"}
ADDRESS_RE = r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"


class HunterBttConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return HunterBttOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not re.match(ADDRESS_RE, address):
                errors[CONF_ADDRESS] = "bad_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_OUTLETS: int(user_input[CONF_OUTLETS]),
                    },
                )

        wanted = {codec.SERVICE, codec.OLD_SERVICE}
        seen = {
            info.address: f"{info.name} ({info.address}, {info.rssi} dBm)"
            for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
            if wanted & set(info.service_uuids) and info.address not in self._async_current_ids()
        }
        address_field = vol.In(seen) if seen else str
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): address_field,
                    vol.Required(CONF_NAME, default="Tap timer"): str,
                    vol.Required(CONF_OUTLETS, default="1"): vol.In(OUTLET_CHOICES),
                }
            ),
        )


class HunterBttOptionsFlow(OptionsFlow):
    """Change the number of outlets without removing the timer."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        if user_input is not None:
            data = {**entry.data, CONF_OUTLETS: int(user_input[CONF_OUTLETS])}
            self.hass.config_entries.async_update_entry(entry, data=data)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_OUTLETS, default=str(entry.data.get(CONF_OUTLETS, 1))): vol.In(OUTLET_CHOICES)}
            ),
        )

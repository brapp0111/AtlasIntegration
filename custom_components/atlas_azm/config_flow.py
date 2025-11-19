"""Config flow for Atlas AZM4/AZM8 integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .client import AtlasAZMClient
from .const import (
    CONF_TCP_PORT,
    CONF_UDP_PORT,
    DEFAULT_NAME,
    DEFAULT_TCP_PORT,
    DEFAULT_UDP_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Optional(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): int,
    vol.Optional(CONF_UDP_PORT, default=DEFAULT_UDP_PORT): int,
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = AtlasAZMClient(
        data[CONF_HOST],
        data.get(CONF_TCP_PORT, DEFAULT_TCP_PORT),
        data.get(CONF_UDP_PORT, DEFAULT_UDP_PORT),
    )

    if not await client.connect():
        raise CannotConnect

    await client.disconnect()

    return {"title": data.get(CONF_NAME, DEFAULT_NAME)}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atlas AZM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create unique ID based on host
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""

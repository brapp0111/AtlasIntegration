"""Switch platform for Atlas AZM4/AZM8."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atlas AZM switch entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]

    entities = []

    # Create mute switches for sources
    for source in coordinator.parameters.get("sources", []):
        entities.append(
            AtlasMuteSwitch(
                client,
                coordinator,
                source,
                entry,
                "source"
            )
        )

    # Create mute switches for zones
    for zone in coordinator.parameters.get("zones", []):
        entities.append(
            AtlasMuteSwitch(
                client,
                coordinator,
                zone,
                entry,
                "zone"
            )
        )

    async_add_entities(entities)


class AtlasMuteSwitch(SwitchEntity):
    """Representation of an Atlas AZM mute control."""

    _attr_has_entity_name = True

    def __init__(self, client, coordinator, config, entry, entity_type):
        """Initialize the switch entity."""
        self._client = client
        self._coordinator = coordinator
        self._config = config
        self._entry = entry
        self._entity_type = entity_type
        
        self._index = config["index"]
        self._name_param = config["name_param"]
        self._mute_param = config["mute_param"]
        
        self._entity_name = f"{entity_type.capitalize()} {self._index}"
        self._is_on = False

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_{self._index}_mute"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Subscribe to parameters in batch
        await asyncio.sleep(0.05)  # Rate limit
        await self._client.subscribe_multiple([
            {"param": self._name_param, "fmt": "str"},
            {"param": self._mute_param, "fmt": "val"},
        ], self._handle_update)
        
        # Get initial values
        await self._client.get(self._name_param, "str")
        await self._client.get(self._mute_param, "val")

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self._client.unsubscribe(self._name_param, "str")
        await self._client.unsubscribe(self._mute_param, "val")

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            self._entity_name = data.get("str", f"{self._entity_type.capitalize()} {self._index}")
            
        elif param == self._mute_param:
            self._is_on = bool(data.get("val", 0))

        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._entity_name} Mute"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on (muted)."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch (mute)."""
        await self._client.set(self._mute_param, 1, "val")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch (unmute)."""
        await self._client.set(self._mute_param, 0, "val")

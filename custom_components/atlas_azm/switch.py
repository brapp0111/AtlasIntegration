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

    # Create mute switches for zones, groups, mixes and each source within a mix
    for entity_type, key in (
        ("zone", "zones"),
        ("group", "groups"),
        ("mix", "mixes"),
        ("mix_source", "mix_sources"),
    ):
        for config in coordinator.parameters.get(key, []):
            entities.append(AtlasMuteSwitch(client, coordinator, config, entry, entity_type))

    # Create combine switches for groups (GroupActive combines/uncombines its zones)
    for group in coordinator.parameters.get("groups", []):
        entities.append(
            AtlasMuteSwitch(
                client, coordinator, group, entry, "group", "active_param", "Combine"
            )
        )

    async_add_entities(entities)


class AtlasMuteSwitch(SwitchEntity):
    """Representation of an Atlas AZM on/off control (mute, or group combine)."""

    _attr_has_entity_name = True

    def __init__(
        self, client, coordinator, config, entry, entity_type,
        param_key="mute_param", suffix="Mute",
    ):
        """Initialize the switch entity."""
        self._client = client
        self._coordinator = coordinator
        self._config = config
        self._entry = entry
        self._entity_type = entity_type
        
        self._index = config["index"]
        self._name_param = config["name_param"]
        self._mute_param = config[param_key]
        self._suffix = suffix
        
        self._default_name = config.get("default_name") or f"{entity_type.capitalize()} {self._index}"
        # Extra name part, e.g. the source within a mix
        self._label = f" {config['label']}" if config.get("label") else ""
        self._entity_name = self._default_name
        self._is_on = False
        
        # Set initial name attribute
        self._attr_name = f"{self._entity_name}{self._label} {suffix}"

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_{self._index}_{suffix.lower()}"

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
        try:
            await self._client.unsubscribe(self._name_param, "str", self._handle_update)
            await self._client.unsubscribe(self._mute_param, "val", self._handle_update)
        except (ConnectionError, Exception) as err:
            _LOGGER.debug("Error during unsubscribe for %s: %s", self.entity_id, err)

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            new_name = data.get("str", "")
            # Use custom name if provided, otherwise use default
            self._entity_name = new_name or self._default_name
            self._attr_name = f"{self._entity_name}{self._label} {self._suffix}"
            
        elif param == self._mute_param:
            self._is_on = bool(data.get("val", 0))

        self.async_write_ha_state()



    @property
    def is_on(self) -> bool:
        """Return true if the switch is on (muted, or group combined)."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch (mute, or combine)."""
        try:
            await self._client.set(self._mute_param, 1, "val")
        except ConnectionError as err:
            _LOGGER.error("Failed to turn on %s: %s", self.entity_id, err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch (unmute, or uncombine)."""
        try:
            await self._client.set(self._mute_param, 0, "val")
        except ConnectionError as err:
            _LOGGER.error("Failed to turn off %s: %s", self.entity_id, err)
            raise

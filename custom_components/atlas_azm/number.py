"""Number platform for Atlas AZM4/AZM8."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up Atlas AZM number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]

    entities = []

    # Create gain controls for sources
    for source in coordinator.parameters.get("sources", []):
        entities.append(
            AtlasGainNumber(
                client, 
                coordinator, 
                source, 
                entry, 
                "source"
            )
        )

    # Create gain controls for zones
    for zone in coordinator.parameters.get("zones", []):
        entities.append(
            AtlasGainNumber(
                client, 
                coordinator, 
                zone, 
                entry, 
                "zone"
            )
        )

    async_add_entities(entities)


class AtlasGainNumber(NumberEntity):
    """Representation of an Atlas AZM gain control as a number entity."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = -60.0
    _attr_native_max_value = 12.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "dB"

    def __init__(self, client, coordinator, config, entry, entity_type):
        """Initialize the number entity."""
        self._client = client
        self._coordinator = coordinator
        self._config = config
        self._entry = entry
        self._entity_type = entity_type
        
        self._index = config["index"]
        self._name_param = config["name_param"]
        self._gain_param = config["gain_param"]
        
        self._entity_name = f"{entity_type.capitalize()} {self._index}"
        self._current_value = -60.0
        
        # Set initial name attribute
        self._attr_name = f"{self._entity_name} Gain"

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_{self._index}_gain"
        
        _LOGGER.debug("Number entity initialized: unique_id=%s, name_param=%s, initial_name=%s", 
                      self._attr_unique_id, self._name_param, self._attr_name)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        _LOGGER.debug("Number entity %s being added to hass, subscribing to %s and %s", 
                      self._attr_unique_id, self._name_param, self._gain_param)
        # Subscribe to parameters in batch
        await asyncio.sleep(0.05)  # Rate limit
        await self._client.subscribe_multiple([
            {"param": self._name_param, "fmt": "str"},
            {"param": self._gain_param, "fmt": "val"},
        ], self._handle_update)
        _LOGGER.debug("Number entity %s subscribed successfully", self._attr_unique_id)
        
        # Get initial values
        await self._client.get(self._name_param, "str")
        await self._client.get(self._gain_param, "val")
        _LOGGER.debug("Number entity %s requested initial values", self._attr_unique_id)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self._client.unsubscribe(self._name_param, "str")
        await self._client.unsubscribe(self._gain_param, "val")

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            new_name = data.get("str", "")
            _LOGGER.debug("Number entity %s received name update: '%s'", self._attr_unique_id, new_name)
            # Use custom name if provided, otherwise use default
            if new_name:
                self._entity_name = new_name
                self._attr_name = f"{self._entity_name} Gain"
            else:
                # Keep default name
                self._entity_name = f"{self._entity_type.capitalize()} {self._index}"
                self._attr_name = f"{self._entity_name} Gain"
            
        elif param == self._gain_param:
            self._current_value = data.get("val", -60.0)

        self.async_write_ha_state()



    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self._current_value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._client.set(self._gain_param, value, "val")

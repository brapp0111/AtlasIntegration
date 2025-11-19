"""Sensor platform for Atlas AZM4/AZM8."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
    """Set up Atlas AZM sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]

    entities = []

    # Create meter sensors for sources
    for source in coordinator.parameters.get("sources", []):
        if "meter_param" in source:
            entities.append(
                AtlasMeterSensor(
                    client,
                    coordinator,
                    source,
                    entry,
                    "source"
                )
            )

    async_add_entities(entities)


class AtlasMeterSensor(SensorEntity):
    """Representation of an Atlas AZM audio meter."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "dBFS"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, client, coordinator, config, entry, entity_type):
        """Initialize the sensor."""
        self._client = client
        self._coordinator = coordinator
        self._config = config
        self._entry = entry
        self._entity_type = entity_type
        
        self._index = config["index"]
        self._name_param = config["name_param"]
        self._meter_param = config["meter_param"]
        
        self._entity_name = f"{entity_type.capitalize()} {self._index}"
        self._current_value = -60.0

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_{self._index}_meter"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Subscribe to parameters
        await self._client.subscribe(
            self._name_param, "str", self._handle_update
        )
        await self._client.subscribe(
            self._meter_param, "val", self._handle_update
        )
        
        # Get initial values
        await self._client.get(self._name_param, "str")
        await self._client.get(self._meter_param, "val")

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self._client.unsubscribe(self._name_param, "str")
        await self._client.unsubscribe(self._meter_param, "val")

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            self._entity_name = data.get("str", f"{self._entity_type.capitalize()} {self._index}")
            
        elif param == self._meter_param:
            # Meter updates come via UDP
            self._current_value = data.get("val", -60.0)

        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._entity_name} Level"

    @property
    def native_value(self) -> float:
        """Return the current meter value."""
        return self._current_value

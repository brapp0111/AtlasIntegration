"""Sensor platform for Atlas AZM4/AZM8."""
from __future__ import annotations

import asyncio
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

    # Create meter sensors for sources.
    for source in coordinator.parameters.get("sources", []):
        if source.get("meter_param"):
            entities.append(AtlasMeterSensor(client, source, entry, "source"))

    # Create meter sensors for zones, groups and mixes.
    for entity_type, key in (("zone", "zones"), ("group", "groups"), ("mix", "mixes")):
        for config in coordinator.parameters.get(key, []):
            if config.get("meter_param"):
                entities.append(AtlasMeterSensor(client, config, entry, entity_type))

    async_add_entities(entities)


class AtlasMeterSensor(SensorEntity):
    """Representation of an Atlas AZM source, zone, group or mix meter sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "dBFS"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:signal"

    def __init__(self, client, config, entry, entity_type: str):
        """Initialize the sensor entity."""
        self._client = client
        self._entity_type = entity_type

        self._index = config["index"]
        self._name_param = config["name_param"]
        self._meter_param = config["meter_param"]

        self._display_name = f"{entity_type.capitalize()} {self._index}"
        self._native_value = None

        self._attr_name = f"{self._display_name} Meter"
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_{self._index}_meter"

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to Home Assistant."""
        await asyncio.sleep(0.05)  # Keep subscription bursts gentle.
        await self._client.subscribe_multiple(
            [
                {"param": self._name_param, "fmt": "str"},
                {"param": self._meter_param, "fmt": "val"},
            ],
            self._handle_update,
        )

        await self._client.get(self._name_param, "str")
        await self._client.get(self._meter_param, "val")

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity is about to be removed from Home Assistant."""
        try:
            await self._client.unsubscribe(self._name_param, "str", self._handle_update)
            await self._client.unsubscribe(self._meter_param, "val", self._handle_update)
        except (ConnectionError, Exception) as err:
            _LOGGER.debug("Error during unsubscribe for %s: %s", self.entity_id, err)

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            name = data.get("str", "")
            self._display_name = name if name else f"{self._entity_type.capitalize()} {self._index}"
            self._attr_name = f"{self._display_name} Meter"

        elif param == self._meter_param:
            try:
                self._native_value = float(data.get("val"))
            except (TypeError, ValueError):
                self._native_value = None

        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return current meter value in dBFS."""
        return self._native_value

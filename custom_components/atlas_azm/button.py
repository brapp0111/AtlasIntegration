"""Button platform for Atlas AZM4/AZM8."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VOLUME_STEP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atlas AZM button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]

    entities = []

    # Create volume up/down buttons for each zone and group
    for entity_type, key in (("zone", "zones"), ("group", "groups")):
        for config in coordinator.parameters.get(key, []):
            entities.append(AtlasVolumeButton(client, config, entry, "up", entity_type))
            entities.append(AtlasVolumeButton(client, config, entry, "down", entity_type))

    # Create a recall button for each configured scene
    for scene in coordinator.parameters.get("scenes", []):
        entities.append(AtlasSceneButton(client, scene, entry))

    async_add_entities(entities)


class AtlasVolumeButton(ButtonEntity):
    """Button that bumps a zone's or group's gain up or down by a fixed step."""

    _attr_has_entity_name = True

    def __init__(self, client, zone_config, entry, direction, entity_type="zone"):
        """Initialize the button."""
        self._client = client
        self._direction = direction
        
        self._index = zone_config["index"]
        self._name_param = zone_config["name_param"]
        self._gain_param = zone_config["gain_param"]
        self._step = VOLUME_STEP if direction == "up" else -VOLUME_STEP
        
        self._attr_icon = "mdi:volume-plus" if direction == "up" else "mdi:volume-minus"
        self._label = "Volume Up" if direction == "up" else "Volume Down"
        self._default_name = f"{entity_type.capitalize()} {self._index}"
        self._attr_name = f"{self._default_name} {self._label}"

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_{self._index}_volume_{direction}"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await asyncio.sleep(0.05)  # Rate limit
        await self._client.subscribe(self._name_param, "str", self._handle_update)
        await self._client.get(self._name_param, "str")

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        try:
            await self._client.unsubscribe(self._name_param, "str", self._handle_update)
        except (ConnectionError, Exception) as err:
            _LOGGER.debug("Error during unsubscribe for %s: %s", self.entity_id, err)

    def _handle_update(self, param: str, data: dict):
        """Handle zone or group name updates."""
        zone_name = data.get("str", "") or self._default_name
        self._attr_name = f"{zone_name} {self._label}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Bump the zone or group gain."""
        try:
            await self._client.bump(self._gain_param, self._step, "pct")
        except ConnectionError as err:
            _LOGGER.error("Failed to change volume for %s: %s", self.entity_id, err)
            raise


class AtlasSceneButton(ButtonEntity):
    """Button that recalls a scene on the AZM."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:palette"

    def __init__(self, client, scene_config, entry):
        """Initialize the button."""
        self._client = client
        
        self._index = scene_config["index"]
        self._name_param = scene_config["name_param"]
        self._recall_param = scene_config["recall_param"]
        self._attr_name = f"Scene {scene_config.get('name') or self._index}"

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_scene_{self._index}_recall"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await asyncio.sleep(0.05)  # Rate limit
        await self._client.subscribe(self._name_param, "str", self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        try:
            await self._client.unsubscribe(self._name_param, "str", self._handle_update)
        except (ConnectionError, Exception) as err:
            _LOGGER.debug("Error during unsubscribe for %s: %s", self.entity_id, err)

    def _handle_update(self, param: str, data: dict):
        """Handle scene name updates."""
        self._attr_name = f"Scene {data.get('str', '') or self._index}"
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Recall the scene (action parameter: any set triggers it)."""
        try:
            await self._client.set(self._recall_param, 1, "val")
        except ConnectionError as err:
            _LOGGER.error("Failed to recall scene for %s: %s", self.entity_id, err)
            raise

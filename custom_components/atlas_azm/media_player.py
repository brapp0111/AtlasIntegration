"""Media Player platform for Atlas AZM4/AZM8."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
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
    """Set up Atlas AZM media player entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    coordinator = data["coordinator"]

    entities = []

    # Create media player for each zone and group
    for zone in coordinator.parameters.get("zones", []):
        entities.append(AtlasZoneMediaPlayer(client, coordinator, zone, entry))
    for group in coordinator.parameters.get("groups", []):
        entities.append(AtlasZoneMediaPlayer(client, coordinator, group, entry, "group"))

    async_add_entities(entities)


class AtlasZoneMediaPlayer(MediaPlayerEntity):
    """Representation of an Atlas AZM Zone or Group as a Media Player."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(self, client, coordinator, zone_config, entry, entity_type="zone"):
        """Initialize the media player."""
        self._client = client
        self._coordinator = coordinator
        self._zone_config = zone_config
        self._entry = entry
        
        self._zone_index = zone_config["index"]
        self._name_param = zone_config["name_param"]
        self._gain_param = zone_config["gain_param"]
        self._mute_param = zone_config["mute_param"]
        self._source_param = zone_config.get("source_param")
        
        self._default_name = f"{entity_type.capitalize()} {self._zone_index}"
        self._zone_name = self._default_name
        self._volume = 50  # Percentage (0-100)
        self._is_muted = False
        self._source_index = -1
        # ZoneSource value -> name; sources and mixes share one index space
        self._source_names: dict[int, str] = {
            item["index"]: item.get("name") or f"Source {item['index']}"
            for item in (
                coordinator.parameters.get("sources", [])
                + coordinator.parameters.get("mixes", [])
            )
        }
        self._source_name_params = [
            item["name_param"]
            for item in (
                coordinator.parameters.get("sources", [])
                + coordinator.parameters.get("mixes", [])
            )
        ]

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_{self._zone_index}"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Build subscription list for batch subscription
        params_to_subscribe = [
            {"param": self._name_param, "fmt": "str"},
            {"param": self._gain_param, "fmt": "pct"},
            {"param": self._mute_param, "fmt": "val"},
        ]
        
        if self._source_param:
            params_to_subscribe.append({"param": self._source_param, "fmt": "val"})
        
        # Subscribe to all zone parameters in one request
        await self._client.subscribe_multiple(params_to_subscribe, self._handle_update)
        
        # Small delay to let subscription process
        await asyncio.sleep(0.05)
        
        # Get initial values (batch get would be better but keep simple for now)
        await self._client.get(self._name_param, "str")
        await self._client.get(self._gain_param, "pct")
        await self._client.get(self._mute_param, "val")
        if self._source_param:
            await self._client.get(self._source_param, "val")
        
        # Keep the source list current - subscribe to source and mix names in batch
        source_params = [
            {"param": param, "fmt": "str"} for param in self._source_name_params
        ]
        
        if source_params:
            await asyncio.sleep(0.05)  # Small delay between batches
            await self._client.subscribe_multiple(source_params, self._handle_source_name_update)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        try:
            await self._client.unsubscribe(self._name_param, "str", self._handle_update)
            await self._client.unsubscribe(self._gain_param, "pct", self._handle_update)
            await self._client.unsubscribe(self._mute_param, "val", self._handle_update)
            if self._source_param:
                await self._client.unsubscribe(self._source_param, "val", self._handle_update)
            
            # Unsubscribe from source and mix names
            for param in self._source_name_params:
                await self._client.unsubscribe(param, "str", self._handle_source_name_update)
        except (ConnectionError, Exception) as err:
            _LOGGER.debug("Error during unsubscribe for %s: %s", self.entity_id, err)

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            zone_name = data.get("str", "")
            # Use custom name if provided, otherwise use default
            self._zone_name = zone_name or self._default_name
            
        elif param == self._gain_param:
            # Get percentage directly (0-100), ensure it's numeric
            try:
                self._volume = float(data.get("pct", 50))
            except (ValueError, TypeError):
                self._volume = 50
            
        elif param == self._mute_param:
            self._is_muted = bool(data.get("val", 0))
            
        elif param == self._source_param:
            # Ensure source index is an integer (-1 = no source)
            try:
                self._source_index = int(data.get("val", -1))
            except (ValueError, TypeError):
                self._source_index = -1

        self.async_write_ha_state()

    def _handle_source_name_update(self, param: str, data: dict):
        """Handle source and mix name updates."""
        # Extract index from param name (e.g., "SourceName_3" -> 3, "MixName_14" -> 14)
        try:
            index = int(param.split("_")[-1])
        except ValueError:
            return
        self._source_names[index] = data.get("str", "") or f"Source {index}"
            
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._zone_name

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the entity."""
        if self._is_muted:
            return MediaPlayerState.OFF
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Return volume level (0..1)."""
        # Convert percentage (0-100) to Home Assistant scale (0-1)
        try:
            volume = float(self._volume)
            return max(0.0, min(1.0, volume / 100.0))
        except (ValueError, TypeError):
            return 0.5

    @property
    def is_volume_muted(self) -> bool:
        """Return boolean if volume is muted."""
        return self._is_muted

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._source_names.get(self._source_index)

    @property
    def source_list(self) -> list[str]:
        """Return the list of available input sources."""
        return [self._source_names[index] for index in sorted(self._source_names)]

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        try:
            # Convert Home Assistant scale (0-1) to percentage (0-100)
            pct_value = int(volume * 100)
            await self._client.set(self._gain_param, pct_value, "pct")
        except ConnectionError as err:
            _LOGGER.error("Failed to set volume for %s: %s", self.entity_id, err)
            raise

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the zone or group."""
        try:
            await self._client.set(self._mute_param, 1 if mute else 0, "val")
        except ConnectionError as err:
            _LOGGER.error("Failed to mute/unmute %s: %s", self.entity_id, err)
            raise

    async def async_volume_up(self) -> None:
        """Increase volume by one step."""
        try:
            await self._client.bump(self._gain_param, VOLUME_STEP, "pct")
        except ConnectionError as err:
            _LOGGER.error("Failed to increase volume for %s: %s", self.entity_id, err)
            raise

    async def async_volume_down(self) -> None:
        """Decrease volume by one step."""
        try:
            await self._client.bump(self._gain_param, -VOLUME_STEP, "pct")
        except ConnectionError as err:
            _LOGGER.error("Failed to decrease volume for %s: %s", self.entity_id, err)
            raise

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        try:
            for source_index, name in self._source_names.items():
                if name == source and self._source_param:
                    await self._client.set(self._source_param, source_index, "val")
                    break
        except ConnectionError as err:
            _LOGGER.error("Failed to select source for %s: %s", self.entity_id, err)
            raise

    async def async_turn_on(self) -> None:
        """Turn on (unmute) the zone."""
        await self.async_mute_volume(False)

    async def async_turn_off(self) -> None:
        """Turn off (mute) the zone."""
        await self.async_mute_volume(True)

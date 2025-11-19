"""Media Player platform for Atlas AZM4/AZM8."""
from __future__ import annotations

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

from .const import DOMAIN

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

    # Create media player for each zone
    for zone in coordinator.parameters.get("zones", []):
        entities.append(AtlasZoneMediaPlayer(client, coordinator, zone, entry))

    async_add_entities(entities)


class AtlasZoneMediaPlayer(MediaPlayerEntity):
    """Representation of an Atlas AZM Zone as a Media Player."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(self, client, coordinator, zone_config, entry):
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
        
        self._zone_name = f"Zone {self._zone_index}"
        self._volume = 0.5  # 0-1 scale
        self._is_muted = False
        self._source_index = 0
        self._available_sources = []

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_zone_{self._zone_index}"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Subscribe to zone parameters
        await self._client.subscribe(
            self._name_param, "str", self._handle_update
        )
        await self._client.subscribe(
            self._gain_param, "val", self._handle_update
        )
        await self._client.subscribe(
            self._mute_param, "val", self._handle_update
        )
        
        if self._source_param:
            await self._client.subscribe(
                self._source_param, "val", self._handle_update
            )
        
        # Get initial values
        await self._client.get(self._name_param, "str")
        await self._client.get(self._gain_param, "val")
        await self._client.get(self._mute_param, "val")
        
        # Build source list
        for source in self._coordinator.parameters.get("sources", []):
            source_name_param = source["name_param"]
            await self._client.subscribe(
                source_name_param, "str", self._handle_source_name_update
            )
            await self._client.get(source_name_param, "str")

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self._client.unsubscribe(self._name_param, "str")
        await self._client.unsubscribe(self._gain_param, "val")
        await self._client.unsubscribe(self._mute_param, "val")
        if self._source_param:
            await self._client.unsubscribe(self._source_param, "val")

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            self._zone_name = data.get("str", f"Zone {self._zone_index}")
            
        elif param == self._gain_param:
            # Convert dB to 0-1 scale (assuming -60 to 0 dB range)
            db_value = data.get("val", -60)
            self._volume = max(0, min(1, (db_value + 60) / 60))
            
        elif param == self._mute_param:
            self._is_muted = bool(data.get("val", 0))
            
        elif param == self._source_param:
            self._source_index = data.get("val", 0)

        self.async_write_ha_state()

    def _handle_source_name_update(self, param: str, data: dict):
        """Handle source name updates."""
        source_name = data.get("str", "Unknown")
        
        # Extract source index from param name (e.g., "SourceName_3" -> 3)
        try:
            source_index = int(param.split("_")[-1])
            
            # Update or append to available sources
            while len(self._available_sources) <= source_index:
                self._available_sources.append(f"Source {len(self._available_sources)}")
            
            self._available_sources[source_index] = source_name
            
        except (ValueError, IndexError):
            pass
            
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
        return self._volume

    @property
    def is_volume_muted(self) -> bool:
        """Return boolean if volume is muted."""
        return self._is_muted

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        if 0 <= self._source_index < len(self._available_sources):
            return self._available_sources[self._source_index]
        return None

    @property
    def source_list(self) -> list[str]:
        """Return the list of available input sources."""
        return self._available_sources

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        # Convert 0-1 scale to dB (-60 to 0)
        db_value = (volume * 60) - 60
        await self._client.set(self._gain_param, db_value, "val")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the zone."""
        await self._client.set(self._mute_param, 1 if mute else 0, "val")

    async def async_volume_up(self) -> None:
        """Increase volume by 1 dB."""
        await self._client.bump(self._gain_param, 1, "val")

    async def async_volume_down(self) -> None:
        """Decrease volume by 1 dB."""
        await self._client.bump(self._gain_param, -1, "val")

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        if source in self._available_sources:
            source_index = self._available_sources.index(source)
            if self._source_param:
                await self._client.set(self._source_param, source_index, "val")

    async def async_turn_on(self) -> None:
        """Turn on (unmute) the zone."""
        await self.async_mute_volume(False)

    async def async_turn_off(self) -> None:
        """Turn off (mute) the zone."""
        await self.async_mute_volume(True)

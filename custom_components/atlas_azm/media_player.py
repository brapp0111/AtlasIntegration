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

    _attr_has_entity_name = False
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
        self._volume = 50  # Percentage (0-100)
        self._is_muted = False
        self._source_index = 0
        self._available_sources = []

        # Generate unique ID
        self._attr_unique_id = f"{entry.entry_id}_zone_{self._zone_index}"

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
        
        # Build source list - subscribe to source names in batch
        source_params = []
        for source in self._coordinator.parameters.get("sources", []):
            source_params.append({"param": source["name_param"], "fmt": "str"})
        
        if source_params:
            await asyncio.sleep(0.05)  # Small delay between batches
            await self._client.subscribe_multiple(source_params, self._handle_source_name_update)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self._client.unsubscribe(self._name_param, "str")
        await self._client.unsubscribe(self._gain_param, "pct")
        await self._client.unsubscribe(self._mute_param, "val")
        if self._source_param:
            await self._client.unsubscribe(self._source_param, "val")

    def _handle_update(self, param: str, data: dict):
        """Handle parameter updates."""
        if param == self._name_param:
            self._zone_name = data.get("str", f"Zone {self._zone_index}")
            
        elif param == self._gain_param:
            # Get percentage directly (0-100), ensure it's numeric
            try:
                self._volume = float(data.get("pct", 50))
            except (ValueError, TypeError):
                self._volume = 50
            
        elif param == self._mute_param:
            self._is_muted = bool(data.get("val", 0))
            
        elif param == self._source_param:
            # Ensure source index is an integer
            self._source_index = int(data.get("val", 0))

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
        try:
            if (isinstance(self._source_index, (int, float)) and 
                0 <= int(self._source_index) < len(self._available_sources)):
                return self._available_sources[int(self._source_index)]
        except (ValueError, IndexError, TypeError):
            pass
        return None

    @property
    def source_list(self) -> list[str]:
        """Return the list of available input sources."""
        return self._available_sources

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0..1)."""
        # Convert Home Assistant scale (0-1) to percentage (0-100)
        pct_value = int(volume * 100)
        await self._client.set(self._gain_param, pct_value, "pct")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the zone."""
        await self._client.set(self._mute_param, 1 if mute else 0, "val")

    async def async_volume_up(self) -> None:
        """Increase volume by 5%."""
        await self._client.bump(self._gain_param, 5, "pct")

    async def async_volume_down(self) -> None:
        """Decrease volume by 5%."""
        await self._client.bump(self._gain_param, -5, "pct")

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

"""The Atlas AZM4/AZM8 integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AtlasAZMClient
from .const import (
    CONF_TCP_PORT,
    CONF_UDP_PORT,
    DEFAULT_TCP_PORT,
    DEFAULT_CHANNELS,
    DEFAULT_UDP_PORT,
    DISCOVERY_MAX_INDEX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atlas AZM from a config entry."""
    host = entry.data[CONF_HOST]
    tcp_port = entry.data.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)
    udp_port = entry.data.get(CONF_UDP_PORT, DEFAULT_UDP_PORT)

    client = AtlasAZMClient(host, tcp_port, udp_port)

    # Connect to the device
    if not await client.connect():
        raise ConfigEntryNotReady(f"Failed to connect to Atlas AZM at {host}")

    # Create coordinator
    coordinator = AtlasAZMCoordinator(hass, client, entry)

    # Discover available parameters
    await coordinator.async_discover_parameters()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: AtlasAZMClient = data["client"]
        await client.disconnect()

    return unload_ok


class AtlasAZMCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Atlas AZM data."""

    def __init__(
        self, 
        hass: HomeAssistant, 
        client: AtlasAZMClient, 
        entry: ConfigEntry
    ):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self.entry = entry
        self.parameters: dict[str, dict] = {}
        
    async def async_discover_parameters(self):
        """Discover which sources, zones, mixes and scenes the device has.

        Unused sources/zones/scenes answer with an empty name; missing mixes,
        zones and scenes answer with an error. Either way they are skipped.
        """
        names = {
            prefix: await self._async_get_names(prefix)
            for prefix in ("SourceName", "ZoneName", "MixName", "SceneName")
        }

        # Older firmware that ignores request ids: fall back to 8 sources/zones
        if not names["SourceName"] and not names["ZoneName"]:
            _LOGGER.warning("Parameter discovery got no replies; assuming 8 sources and 8 zones")
            names["SourceName"] = {i: "" for i in range(DEFAULT_CHANNELS)}
            names["ZoneName"] = {i: "" for i in range(DEFAULT_CHANNELS)}

        self.parameters = {
            "sources": [
                {
                    "index": i,
                    "name": name,
                    "name_param": f"SourceName_{i}",
                    "gain_param": f"SourceGain_{i}",
                    "mute_param": f"SourceMute_{i}",
                    "meter_param": f"SourceMeter_{i}",
                }
                for i, name in names["SourceName"].items()
            ],
            "zones": [
                {
                    "index": i,
                    "name": name,
                    "name_param": f"ZoneName_{i}",
                    "gain_param": f"ZoneGain_{i}",
                    "mute_param": f"ZoneMute_{i}",
                    "source_param": f"ZoneSource_{i}",
                    "active_param": f"ZoneActive_{i}",
                    "meter_param": f"ZoneMeter_{i}",
                }
                for i, name in names["ZoneName"].items()
            ],
            # Mixes can be picked as a zone source, using the mix index
            "mixes": [
                {"index": i, "name": name, "name_param": f"MixName_{i}"}
                for i, name in names["MixName"].items()
            ],
            "scenes": [
                {
                    "index": i,
                    "name": name,
                    "name_param": f"SceneName_{i}",
                    "recall_param": f"RecallScene_{i}",
                }
                for i, name in names["SceneName"].items()
            ],
            "groups": [],
        }

        _LOGGER.info(
            "Discovered %d sources, %d zones, %d mixes and %d scenes",
            len(self.parameters["sources"]),
            len(self.parameters["zones"]),
            len(self.parameters["mixes"]),
            len(self.parameters["scenes"]),
        )

    async def _async_get_names(self, prefix: str) -> dict[int, str]:
        """Return {index: name} for every configured parameter with this name prefix."""
        results = await asyncio.gather(
            *(self.client.get_name(f"{prefix}_{i}") for i in range(DISCOVERY_MAX_INDEX)),
            return_exceptions=True,
        )
        return {
            i: name
            for i, name in enumerate(results)
            if isinstance(name, str) and name
        }

    async def _async_update_data(self):
        """Fetch data from API endpoint.
        
        This is not really needed for Atlas AZM since it uses push updates,
        but we keep it for connection health checks.
        """
        try:
            if not self.client.is_connected:
                raise UpdateFailed("Connection lost to Atlas AZM")
            return self.data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

# Atlas AZM4/AZM8 Home Assistant Integration

A custom Home Assistant integration for controlling Atlas Sound AZM4/AZM8 audio matrix processors via their JSON-RPC 2.0 API over TCP/UDP.

## Features

- **Media Player Entities**: Control zones as media players with volume, mute, and source selection
- **Number Entities**: Fine-tune gain levels for sources and zones in dB
- **Sensor Entities**: Monitor real-time audio levels via UDP
- **Switch Entities**: Quick mute/unmute controls for sources and zones
- **Real-time Updates**: Automatic push updates via subscriptions (no polling)
- **Automatic Discovery**: Discovers available sources, zones, and groups
- **Optimized Communication**: Batch subscriptions and rate limiting to prevent overwhelming the device

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/brapp0111/AtlasIntegration` and select "Integration" as the category
6. Click "Add"
7. Search for "Atlas AZM4/AZM8" in HACS
8. Click "Download"
9. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/atlas_azm` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### Via UI (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Atlas AZM4/AZM8"
4. Enter the following information:
   - **Host**: IP address of your AZM4/AZM8 device
   - **Name**: Friendly name for the integration (default: "Atlas AZM")
   - **TCP Port**: Control port (default: 5321)
   - **UDP Port**: Meter updates port (default: 3131)
5. Click **Submit**

### Via configuration.yaml (Not Supported)

This integration only supports configuration via the UI.

## Usage

### Media Player Controls

Each zone appears as a Media Player entity with the following capabilities:

- **Volume Control**: Adjust zone volume (converts between 0-1 scale and -60 to 0 dB)
- **Mute/Unmute**: Quickly silence or enable a zone
- **Source Selection**: Choose which source feeds the zone
- **Turn On/Off**: Unmute/mute the zone

Example automation:
```yaml
automation:
  - alias: "Morning Audio"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: media_player.select_source
        target:
          entity_id: media_player.atlas_azm_zone_0
        data:
          source: "Music Player"
      - service: media_player.volume_set
        target:
          entity_id: media_player.atlas_azm_zone_0
        data:
          volume_level: 0.5
```

### Number Controls

Fine-tune gain levels with precise dB control:

- **Range**: -60 dB to +12 dB
- **Step**: 0.5 dB increments
- **Available for**: All sources and zones

Example:
```yaml
service: number.set_value
target:
  entity_id: number.atlas_azm_source_0_gain
data:
  value: -12.5
```

### Audio Level Sensors

Monitor real-time audio levels (updated via UDP):

- **Unit**: dBFS (decibels relative to full scale)
- **Update Rate**: Real-time via UDP push
- **Available for**: All sources

### Mute Switches

Quick mute controls:

- **Switch On**: Mute
- **Switch Off**: Unmute
- **Available for**: All sources and zones

## Protocol Details

This integration implements the Atlas AZM JSON-RPC 2.0 protocol:

- **TCP Port 5321**: Parameter control, subscriptions, and non-meter updates
- **UDP Port 3131**: Real-time meter updates
- **Keep-alive**: Automatic every 4 minutes to maintain connection
- **Message Format**: JSON-RPC 2.0 with newline delimiters (`\n`)

### Supported Methods

- `set`: Set parameter values
- `bmp` (bump): Increment/decrement values
- `sub`: Subscribe to parameter updates
- `unsub`: Unsubscribe from updates
- `get`: Get current value (one-time query)

### Example Messages

**Set zone volume:**
```json
{"jsonrpc":"2.0","method":"set","params":{"param":"ZoneGain_0","val":-20}}\n
```

**Subscribe to source meter:**
```json
{"jsonrpc":"2.0","method":"sub","params":{"param":"SourceMeter_0","fmt":"val"}}\n
```

**Keep-alive:**
```json
{"jsonrpc":"2.0","method":"get","params":{"param":"KeepAlive","fmt":"str"}}\n
```

## Parameter Naming Convention

The integration uses the Atlas third-party parameter naming scheme:

- **Sources**: `SourceName_X`, `SourceGain_X`, `SourceMute_X`, `SourceMeter_X`
- **Zones**: `ZoneName_X`, `ZoneGain_X`, `ZoneMute_X`, `ZoneSource_X`
- **Groups**: `GroupName_X`, `GroupActive_X`

Where `X` is the 0-based index.

## Troubleshooting

### Connection Issues

1. **Verify network connectivity**: Ensure Home Assistant can reach the AZM device
2. **Check ports**: Confirm TCP 5321 and UDP 3131 are not blocked by firewall
3. **Review logs**: Check Home Assistant logs for connection errors

### Entity Not Updating

1. **Check subscriptions**: The integration automatically subscribes to all parameters
2. **Connection timeout**: If inactive for >5 minutes, the device may drop the connection
3. **Restart integration**: Reload the integration from the UI

### Debugging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.atlas_azm: debug
```

## Advanced Usage

### Services

All standard Home Assistant services for media players, numbers, sensors, and switches are supported.

### Attributes

Each entity exposes additional attributes:

- Media Players: `source`, `source_list`, `volume_level`, `is_volume_muted`
- Numbers: `min`, `max`, `step`, `unit_of_measurement`
- Sensors: `unit_of_measurement`, `state_class`

## Limitations

- **Name Parameters**: Source/Zone names cannot be set via the integration (read-only from device)
- **Group Management**: Zone groups are supported but combining/uncombining requires specific handling
- **Action Parameters**: Scene recall and message playback use the `set` method but don't maintain state

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This integration is provided as-is under the MIT License.

## Credits

Developed for Atlas Sound AZM4/AZM8 audio matrix processors based on their third-party control protocol documentation.

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Check Home Assistant community forums

## Compatibility

- **Home Assistant**: 2023.1 or newer
- **Devices**: Atlas Sound AZM4, AZM8
- **Python**: 3.10 or newer

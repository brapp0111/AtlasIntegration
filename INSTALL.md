# Installation Instructions

## Quick Start

1. Copy the entire `custom_components/atlas_azm` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Atlas AZM4/AZM8"
5. Enter your device's IP address and configure

## Directory Structure

```
custom_components/
└── atlas_azm/
    ├── __init__.py          # Integration setup and coordinator
    ├── client.py            # TCP/UDP JSON-RPC client
    ├── config_flow.py       # UI configuration flow
    ├── const.py             # Constants and defaults
    ├── manifest.json        # Integration metadata
    ├── media_player.py      # Zone media player entities
    ├── number.py            # Gain control entities
    ├── sensor.py            # Audio meter sensors
    ├── strings.json         # UI strings
    ├── switch.py            # Mute switch entities
    └── translations/
        └── en.json          # English translations
```

## Requirements

- Home Assistant 2023.1 or newer
- Network connectivity to AZM4/AZM8 device
- Ports 5321 (TCP) and 3131 (UDP) accessible

## First-Time Setup

After adding the integration:

1. **Verify Connection**: Check that all entities appear in the device page
2. **Test Controls**: Try adjusting a zone volume to confirm communication
3. **Configure Automations**: Use the entities in your automations and scripts

## Updating

To update the integration:

1. Replace the `custom_components/atlas_azm` folder with the new version
2. Restart Home Assistant
3. The integration will automatically update

## Uninstalling

1. Go to Settings → Devices & Services
2. Find the Atlas AZM integration
3. Click the three dots → Delete
4. Optionally remove the `custom_components/atlas_azm` folder
5. Restart Home Assistant

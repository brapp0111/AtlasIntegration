# Example Automations and Scripts

## Basic Examples

### Morning Audio Schedule

```yaml
automation:
  - alias: "Morning Music"
    description: "Start music in kitchen at 7am"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: media_player.select_source
        target:
          entity_id: media_player.atlas_azm_kitchen
        data:
          source: "Music Player"
      - service: media_player.volume_set
        target:
          entity_id: media_player.atlas_azm_kitchen
        data:
          volume_level: 0.3  # 30% volume (-42 dB)
```

### Doorbell Chime

```yaml
automation:
  - alias: "Doorbell Announcement"
    description: "Play doorbell chime in all zones"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door_button
        to: "on"
    action:
      # Temporarily lower music volume
      - service: number.set_value
        target:
          entity_id: number.atlas_azm_music_player_gain
        data:
          value: -20
      # Wait for chime to finish
      - delay: "00:00:03"
      # Restore music volume
      - service: number.set_value
        target:
          entity_id: number.atlas_azm_music_player_gain
        data:
          value: -6
```

### Audio Level Monitoring

```yaml
automation:
  - alias: "High Audio Level Alert"
    description: "Notify when source level is too high"
    trigger:
      - platform: numeric_state
        entity_id: sensor.atlas_azm_microphone_level
        above: -3  # -3 dBFS
    action:
      - service: notify.mobile_app
        data:
          message: "Warning: Microphone audio level is too high!"
          title: "Audio Alert"
```

### Automatic Muting

```yaml
automation:
  - alias: "Mute During Meeting"
    description: "Automatically mute background music during calendar events"
    trigger:
      - platform: state
        entity_id: calendar.work_meetings
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: 
            - switch.atlas_azm_lobby_mute
            - switch.atlas_azm_conference_room_mute
```

## Advanced Examples

### Scene-Based Control

```yaml
script:
  presentation_mode:
    alias: "Presentation Mode"
    sequence:
      # Mute music sources
      - service: switch.turn_on
        target:
          entity_id:
            - switch.atlas_azm_music_player_mute
            - switch.atlas_azm_radio_mute
      # Set microphone gain
      - service: number.set_value
        target:
          entity_id: number.atlas_azm_podium_mic_gain
        data:
          value: -3
      # Route mic to all zones
      - service: media_player.select_source
        target:
          entity_id:
            - media_player.atlas_azm_main_room
            - media_player.atlas_azm_overflow_room
        data:
          source: "Podium Mic"
      # Set zone volumes
      - service: media_player.volume_set
        target:
          entity_id: media_player.atlas_azm_main_room
        data:
          volume_level: 0.7
      - service: media_player.volume_set
        target:
          entity_id: media_player.atlas_azm_overflow_room
        data:
          volume_level: 0.5
```

### Dynamic Volume Based on Time

```yaml
automation:
  - alias: "Dynamic Background Music Volume"
    description: "Adjust volume based on time of day"
    trigger:
      - platform: time_pattern
        hours: "/1"  # Every hour
    action:
      - choose:
          # Early morning (6-8 AM): Low volume
          - conditions:
              - condition: time
                after: "06:00:00"
                before: "08:00:00"
            sequence:
              - service: media_player.volume_set
                target:
                  entity_id: media_player.atlas_azm_lobby
                data:
                  volume_level: 0.2
          # Business hours (8 AM - 5 PM): Medium volume
          - conditions:
              - condition: time
                after: "08:00:00"
                before: "17:00:00"
            sequence:
              - service: media_player.volume_set
                target:
                  entity_id: media_player.atlas_azm_lobby
                data:
                  volume_level: 0.35
          # Evening (5-10 PM): Lower volume
          - conditions:
              - condition: time
                after: "17:00:00"
                before: "22:00:00"
            sequence:
              - service: media_player.volume_set
                target:
                  entity_id: media_player.atlas_azm_lobby
                data:
                  volume_level: 0.25
        default:
          # Night/off hours: Muted
          - service: media_player.turn_off
            target:
              entity_id: media_player.atlas_azm_lobby
```

### Volume Fade Script

```yaml
script:
  fade_volume:
    alias: "Fade Volume"
    description: "Gradually fade volume up or down"
    fields:
      entity_id:
        description: "Media player entity"
        example: "media_player.atlas_azm_zone_0"
      target_volume:
        description: "Target volume level (0.0 - 1.0)"
        example: 0.5
      duration:
        description: "Fade duration in seconds"
        example: 10
    sequence:
      - repeat:
          count: "{{ duration }}"
          sequence:
            - service: media_player.volume_set
              target:
                entity_id: "{{ entity_id }}"
              data:
                volume_level: >
                  {% set current = state_attr(entity_id, 'volume_level') | float %}
                  {% set target = target_volume | float %}
                  {% set step = (target - current) / duration %}
                  {{ (current + step) | float }}
            - delay: "00:00:01"
```

### Lovelace Dashboard Card

```yaml
type: entities
title: Atlas Audio Control
entities:
  - entity: media_player.atlas_azm_main_zone
    name: Main Zone
  - type: attribute
    entity: media_player.atlas_azm_main_zone
    attribute: source
    name: Current Source
  - entity: number.atlas_azm_main_zone_gain
    name: Main Zone Gain
  - entity: switch.atlas_azm_main_zone_mute
    name: Mute Main Zone
  - entity: sensor.atlas_azm_microphone_level
    name: Mic Level
  - type: divider
  - entity: media_player.atlas_azm_overflow_zone
    name: Overflow Zone
  - entity: number.atlas_azm_overflow_zone_gain
    name: Overflow Zone Gain
```

## Tips

1. **Volume Conversion**: Home Assistant uses 0-1 scale, which the integration converts to -60 to 0 dB
2. **Gain Precision**: Use number entities for precise dB control instead of media player volume
3. **Real-time Meters**: Sensor entities update in real-time via UDP for live monitoring
4. **Mute vs Off**: Using `turn_off` on media players mutes them; use switches for explicit mute control

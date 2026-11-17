# BLRV Atlas AZM message table

Read from the Atlas web UI (http://192.168.10.50, Settings > Third Party Control > Message Table) on 2026-11-17.
Parameter names can change if zones/sources/mixes are added or removed on the Atlas.

Ranges (from ATS006993-B section 6.0): Gain and Meter -80 to 0 dB (`val`), 0 to 100 (`pct`). Mute 0/1. ZoneSource/GroupSource -1 (none) to source number.

## Sources
| Name | Index |
|---|---|
| HDMI-in 1 | 0 |
| HDMI-in 2 | 1 |
| A-XLR | 2 |
| B-XLR | 3 |
| RCA | 4 |
| Sonos | 5 |
| WiiM | 6 |

Params: `SourceGain_N`, `SourceMeter_N`, `SourceMute_N`, `SourceName_N`.

## Mixes
| Name | Index | Sources in mix |
|---|---|---|
| HDMIinBoth | 14 | HDMI-in 1, HDMI-in 2 |
| HDMI/Mics/XLR/RCA | 15 | HDMI-in 1, A-XLR, B-XLR, RCA |
| Mics Only XLR A/B | 16 | A-XLR, B-XLR |
| Mics/WiiM | 17 | A-XLR, B-XLR, WiiM |

Params: `MixGain_N`, `MixMeter_N`, `MixMute_N`, `MixName_N`; per-source in mix: `Mix_N_SourceGain_S`, `Mix_N_SourceMute_S`.

## Zones
| Name | Index |
|---|---|
| Gathering Hall East | 0 |
| Gathering Hall West | 1 |
| Clubhouse Internal | 2 |
| East Patio | 3 |
| West Patio | 4 |
| Dock | 5 |
| Pool / Gazebo | 6 |

Params: `ZoneGain_N`, `ZoneMeter_N`, `ZoneMute_N`, `ZoneName_N`, `ZoneSource_N`.

## Groups
| Name | Index |
|---|---|
| HDMI Gathering Hall | 0 |

Params: `GroupGain_0`, `GroupMeter_0`, `GroupMute_0`, `GroupName_0`, `GroupSource_0`, `GroupActive_0`.

## Scenes
| Name | Index |
|---|---|
| Music Outside Sonos | 0 |
| Music Outside WiiM | 1 |
| Mic Only | 2 |
| Music Only | 3 |
| Newmar | 4 |

Params: `SceneName_N`, `RecallScene_N`.

## Misc
- Bell schedule: `TodaysBellSchedule`
- GPO status: `GPOState_0`, `GPOState_1`
- Loud noise status: `LoudNoise_1`..`LoudNoise_6`, `LoudNoise_8` (as listed by the UI)

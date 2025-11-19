# Atlas AZM4/AZM8 Protocol Reference

This document details the JSON-RPC 2.0 protocol implementation for Atlas Sound AZM4/AZM8 audio processors.

## Connection Details

### TCP Connection (Port 5321)
- Used for parameter modifications, subscriptions, and most responses
- Persistent connection required for subscriptions
- Connection lost = all subscriptions cleared

### UDP Connection (Port 3131)
- Used exclusively for meter subscription updates
- Real-time audio level data
- Connectionless protocol

### Keep-Alive Mechanism

**Requirement**: Send keep-alive at least every 5 minutes to prevent timeout

**Message**:
```json
{"jsonrpc":"2.0","method":"get","params":{"param":"KeepAlive","fmt":"str"}}\n
```

**Responses**:
- TCP: `{"jsonrpc":"2.0","method":"getResp","params":[{"param":"KeepAlive","str":"OK"}]}`
- UDP: `{"jsonrpc":"2.0","method":"getResp","params":[{"param":"KeepAlive","str":"OK"}]}`

## Message Format

### General Rules
1. All messages must be newline delimited (`\n`)
2. JSON-RPC 2.0 compliant
3. Case-sensitive parameter names

### Message Structure

```json
{
  "jsonrpc": "2.0",
  "method": "<method_name>",
  "params": {<parameters>},
  "id": <optional_id>
}
```

## Methods

### Client to Device

#### 1. set - Set Parameter Value

Sets a parameter to an absolute value.

```json
{"jsonrpc":"2.0","method":"set","params":{"param":"<param_name>","<fmt>":"<value>"}}\n
```

**Example**:
```json
{"jsonrpc":"2.0","method":"set","params":{"param":"ZoneGain_0","val":-20}}\n
{"jsonrpc":"2.0","method":"set","params":{"param":"SourceMute_1","val":1}}\n
{"jsonrpc":"2.0","method":"set","params":{"param":"ZoneSource_0","val":3}}\n
```

#### 2. bmp - Bump Parameter Value

Increments or decrements a parameter by a relative value.

```json
{"jsonrpc":"2.0","method":"bmp","params":{"param":"<param_name>","<fmt>":<delta>}}\n
```

**Example**:
```json
{"jsonrpc":"2.0","method":"bmp","params":{"param":"SourceGain_0","val":-1}}\n
{"jsonrpc":"2.0","method":"bmp","params":{"param":"ZoneGain_2","val":2}}\n
```

#### 3. sub - Subscribe to Parameter

Subscribes to automatic updates when parameter changes.

```json
{"jsonrpc":"2.0","method":"sub","params":{"param":"<param_name>","fmt":"<format>"}}\n
```

**Example**:
```json
{"jsonrpc":"2.0","method":"sub","params":{"param":"SourceMeter_0","fmt":"val"}}\n
{"jsonrpc":"2.0","method":"sub","params":{"param":"ZoneName_0","fmt":"str"}}\n
```

#### 4. unsub - Unsubscribe from Parameter

Stops receiving updates for a parameter.

```json
{"jsonrpc":"2.0","method":"unsub","params":{"param":"<param_name>","fmt":"<format>"}}\n
```

**Example**:
```json
{"jsonrpc":"2.0","method":"unsub","params":{"param":"SourceMeter_3","fmt":"val"}}\n
```

#### 5. get - Get Parameter Value

One-time query for current parameter value.

```json
{"jsonrpc":"2.0","method":"get","params":{"param":"<param_name>","fmt":"<format>"}}\n
```

**Example**:
```json
{"jsonrpc":"2.0","method":"get","params":{"param":"ZoneGain_0","fmt":"val"}}\n
{"jsonrpc":"2.0","method":"get","params":{"param":"SourceName_1","fmt":"str"}}\n
```

### Device to Client

#### 1. update - Parameter Update

Sent when a subscribed parameter changes.

```json
{"jsonrpc":"2.0","method":"update","params":[{"param":"<param_name>","<fmt>":<value>}]}
```

**Example**:
```json
{"jsonrpc":"2.0","method":"update","params":[{"param":"ZoneGain_0","val":-15.5}]}
{"jsonrpc":"2.0","method":"update","params":[{"param":"SourceMeter_0","val":-12.3}]}
```

#### 2. getResp - Get Response

Response to `get` method.

```json
{"jsonrpc":"2.0","method":"getResp","params":[{"param":"<param_name>","<fmt>":<value>}]}
```

#### 3. error - Error Message

Sent when an error occurs.

```json
{"jsonrpc":"2.0","method":"error","params":{"message":"<error_message>"}}
```

## Format Types

- `val`: Numeric value (integer or float)
- `str`: String value
- `pct`: Percentage value (0-100)

## Array Operations

Multiple parameters can be included in a single message using arrays.

**Example**:
```json
{"jsonrpc":"2.0","method":"set","params":[
  {"param":"ZoneGain_0","val":-20},
  {"param":"ZoneGain_1","val":-15},
  {"param":"ZoneGain_2","val":-10}
]}\n
```

```json
{"jsonrpc":"2.0","method":"sub","params":[
  {"param":"SourceMeter_0","fmt":"val"},
  {"param":"SourceMeter_1","fmt":"val"},
  {"param":"SourceMeter_2","fmt":"val"}
]}\n
```

## Response with ID

Add `"id"` field to receive explicit confirmation.

**Without ID** (no response):
```json
{"jsonrpc":"2.0","method":"unsub","params":{"param":"GpoPresetName_0","fmt":"str"}}\n
```

**With ID** (receives response):
```json
{"jsonrpc":"2.0","method":"unsub","params":{"param":"GpoPresetName_0","fmt":"str"},"id":10}\n
```

**Response**:
```json
{"jsonrpc":"2.0","result":"OK","id":10}
```

## Parameter Categories

### Sources
- `SourceName_X` (str, read-only): Source name
- `SourceGain_X` (val): Gain in dB (-60 to 12)
- `SourceMute_X` (val): Mute state (0=unmuted, 1=muted)
- `SourceMeter_X` (val): Audio level in dBFS

### Zones
- `ZoneName_X` (str, read-only): Zone name
- `ZoneGain_X` (val): Gain in dB (-60 to 12)
- `ZoneMute_X` (val): Mute state (0=unmuted, 1=muted)
- `ZoneSource_X` (val): Selected source index
- `ZoneActive_X` (val, read-only): Zone active in group

### Groups
- `GroupName_X` (str, read-only): Group name
- `GroupActive_X` (val): Group combine state

### Mixes
- `MixName_X` (str, read-only): Mix name
- Additional mix parameters vary by configuration

## Special Parameters

### Read-Only Parameters
Cannot be set by third-party clients:
- All `*Name_X` parameters
- `ZoneActive_X`

### Action Parameters
Trigger actions when set, but don't maintain state:
- `PlayMessage`
- `RecallScene`
- Other action-based parameters

Subscribing to these provides notification when action is triggered.

## Value Ranges

| Parameter Type | Minimum | Maximum | Unit |
|---------------|---------|---------|------|
| Gain          | -60     | 12      | dB   |
| Mute          | 0       | 1       | bool |
| Source Index  | 0       | 7       | int  |
| Meter Level   | -60     | 0       | dBFS |

## Best Practices

1. **Use Subscriptions**: Don't poll with `get` - subscribe for automatic updates
2. **Batch Operations**: Use arrays for multiple parameter changes
3. **Keep-Alive**: Send every 4 minutes (less than 5 minute timeout)
4. **Error Handling**: Always handle `error` method responses
5. **Connection Management**: Reconnect and resubscribe if connection lost
6. **UDP for Meters**: Audio meters update frequently, UDP reduces overhead

## Implementation Notes

### Subscription Lifecycle
1. Connect TCP (port 5321) and UDP (port 3131)
2. Subscribe to desired parameters
3. Receive updates via TCP (most params) or UDP (meters)
4. Send keep-alive every 4 minutes
5. On disconnect: all subscriptions lost, must resubscribe

### Thread Safety
- TCP writes should be serialized
- UDP receives may arrive asynchronously
- Handle concurrent updates appropriately

### Error Recovery
- Network errors: Reconnect and resubscribe
- Invalid parameters: Check message table for correct names
- Timeout: Connection lost after 5 minutes inactivity

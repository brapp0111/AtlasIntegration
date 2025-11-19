#!/bin/bash

# Test script to query volume levels for all AtlasIED AZM8 zones
# Uses TCP port 5321 with JSON-RPC 2.0 protocol
# Usage: ./test_volume_query.sh <host> [port]
#
# Example: ./test_volume_query.sh 192.168.10.50
#          ./test_volume_query.sh 192.168.10.50 5321

# Check if host is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <host> [port]"
    echo "Example: $0 192.168.10.50"
    echo "Example: $0 192.168.10.50 5321"
    exit 1
fi

HOST="$1"
PORT="${2:-5321}"  # Default to port 5321 (AZM8 control port)

echo "========================================"
echo "AtlasIED AZM8 Volume Query Test"
echo "========================================"
echo "Target: ${HOST}:${PORT}"
echo "Protocol: JSON-RPC 2.0 over TCP"
echo "Date: $(date)"
echo ""

# Function to send JSON-RPC command via TCP and get response
send_jsonrpc() {
    local message="$1"
    # Add newline delimiter required by AZM8
    echo -e "${message}\n" | nc -w 2 "${HOST}" "${PORT}"
}

# Function to query a single zone parameter
query_zone_param() {
    local zone_index=$1  # 0-based index (zone 1 = index 0)
    local param_type=$2  # "Gain", "Mute", "Source", "Name"
    
    local param_name="Zone${param_type}_${zone_index}"
    local message="{\"jsonrpc\":\"2.0\",\"method\":\"get\",\"params\":{\"param\":\"${param_name}\",\"fmt\":\"val\"}}"
    
    send_jsonrpc "$message"
}

# Function to query all parameters for a zone
query_zone() {
    local zone_num=$1
    local zone_index=$((zone_num - 1))  # Convert to 0-based index
    
    echo "Zone ${zone_num} (Index ${zone_index}):"
    
    # Query Gain (Volume)
    echo -n "  Querying ZoneGain_${zone_index}... "
    gain_response=$(query_zone_param ${zone_index} "Gain")
    echo "${gain_response}"
    
    # Query Mute
    echo -n "  Querying ZoneMute_${zone_index}... "
    mute_response=$(query_zone_param ${zone_index} "Mute")
    echo "${mute_response}"
    
    # Query Source
    echo -n "  Querying ZoneSource_${zone_index}... "
    source_response=$(query_zone_param ${zone_index} "Source")
    echo "${source_response}"
    
    # Query Name
    echo -n "  Querying ZoneName_${zone_index}... "
    name_response=$(query_zone_param ${zone_index} "Name")
    echo "${name_response}"
    
    echo ""
}

# Test connection with KeepAlive
echo "Testing connection with KeepAlive..."
echo "----------------------------------------"
keepalive_msg='{"jsonrpc":"2.0","method":"get","params":{"param":"KeepAlive","fmt":"str"}}'
keepalive_response=$(send_jsonrpc "$keepalive_msg")
echo "Request:  ${keepalive_msg}"
echo "Response: ${keepalive_response}"
echo ""

# Query all zones (0-6 based on your configuration - 7 zones shown in the table)
echo "Querying all zones..."
echo "----------------------------------------"
echo ""

# Query zones 0-6 (7 zones total based on the table)
for zone in {1..7}; do
    query_zone $zone
done

echo "========================================"
echo "Query complete!"
echo "========================================"
echo ""
echo "Note: Zone parameters use 0-based indexing"
echo "      Zone 1 = ZoneGain_0, ZoneMute_0, etc."
echo ""
echo "To subscribe to updates, use:"
echo '  {"jsonrpc":"2.0","method":"sub","params":{"param":"ZoneGain_0","fmt":"val"}}'
echo ""
echo "To set a value, use:"
echo '  {"jsonrpc":"2.0","method":"set","params":{"param":"ZoneGain_0","val":-10}}'
echo '  {"jsonrpc":"2.0","method":"set","params":{"param":"ZoneMute_0","val":1}}'

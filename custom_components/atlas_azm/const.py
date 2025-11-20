"""Constants for the Atlas AZM4/AZM8 integration."""

DOMAIN = "atlas_azm"

# Configuration keys
CONF_TCP_PORT = "tcp_port"
CONF_UDP_PORT = "udp_port"

# Default values
DEFAULT_TCP_PORT = 5321
DEFAULT_UDP_PORT = 3131
DEFAULT_NAME = "Atlas AZM"

# Keep-alive interval (seconds)
KEEPALIVE_INTERVAL = 240  # 4 minutes (less than 5 minute timeout)

# Attributes
ATTR_PARAMETER = "parameter"
ATTR_VALUE = "value"

# Platforms
PLATFORMS = ["media_player", "number", "switch"]

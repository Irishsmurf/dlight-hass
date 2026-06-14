"""Constants for the dLight integration."""

from homeassistant.const import Platform

DOMAIN = "dlight"
EVENT_PHYSICAL_CONTROL = "dlight_physical_control"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.EVENT, Platform.LIGHT]

# Extra config-entry key (the IP address uses HA's standard CONF_IP_ADDRESS).
CONF_DEVICE_ID = "device_id"

# How often the coordinator polls each lamp, in seconds.
POLL_INTERVAL = 30

# Hard ceiling for a single poll (state + info queries combined), in seconds.
POLL_TIMEOUT = 10

# White-spectrum range supported by dLight hardware (per vendor docs).
KELVIN_MIN = 2600
KELVIN_MAX = 6000

# Runtime IP self-healing: after this many *consecutive* failed polls the
# coordinator fires a one-shot UDP discovery sweep, looking for the lamp on a
# new address (covers setups where HA's DHCP watcher can't see the lease).
REDISCOVERY_FAILURE_THRESHOLD = 3

# How long a rediscovery sweep listens for UDP answers, in seconds.
REDISCOVERY_DURATION = 2.0

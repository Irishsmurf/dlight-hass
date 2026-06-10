"""Constants for the dLight integration."""
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "dlight"
PLATFORMS = [Platform.LIGHT]

# Extra config-entry key (the IP address uses HA's standard CONF_IP_ADDRESS).
CONF_DEVICE_ID = "device_id"

# How often the coordinator polls each lamp for its current state.
UPDATE_INTERVAL = timedelta(seconds=30)

# Hard ceiling for a single poll (state + info queries combined), in seconds.
POLL_TIMEOUT = 10

# White-spectrum range supported by dLight hardware (per vendor docs).
KELVIN_MIN = 2600
KELVIN_MAX = 6000

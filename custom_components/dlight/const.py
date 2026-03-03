"""Constants for the dLight integration."""
import datetime
from homeassistant.const import Platform

DOMAIN = "dlight"
PLATFORMS = [Platform.LIGHT]

# Polling interval
UPDATE_INTERVAL = datetime.timedelta(seconds=30)

# Config keys
CONF_DEVICE_ID = "device_id"

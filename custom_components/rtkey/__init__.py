import voluptuous as vol
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "rtkey"

PLATFORMS: list[str] = ["image"]

CONF_NAME = "name"
CONF_TOKEN = "token"
CONF_CAMERA_IMAGE_REFRESH_INTERVAL = "camera_image_refresh_interval"

DATA_SCHEMA = {
    vol.Required(CONF_NAME, default="Flat1"): str,
}

OPTIONS_SCHEMA = {
   vol.Required(CONF_TOKEN): str,
   vol.Required(CONF_CAMERA_IMAGE_REFRESH_INTERVAL, default=2): int
}

_LOGGER = logging.getLogger(DOMAIN)
_LOGGER.setLevel(logging.INFO)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    return True

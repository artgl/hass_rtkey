import voluptuous as vol
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "rtkey"

PLATFORMS: list[str] = ["image"]

CONF_NAME = "name"
CONF_TOKEN = "token"
CONF_CAMERA_IMAGE_REFRESH_INTERVAL = "camera_image_refresh_interval"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Flat1"): str,
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_CAMERA_IMAGE_REFRESH_INTERVAL, default=2): int
    }
)

_LOGGER = logging.getLogger(DOMAIN)
_LOGGER.setLevel(logging.INFO)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    _LOGGER.info(["async_setup_entry", config_entry])
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = {
        "name": config_entry.data[CONF_NAME],
        "token": config_entry.data[CONF_TOKEN],
        "camera_image_refresh_interval": config_entry.data[CONF_CAMERA_IMAGE_REFRESH_INTERVAL]
    }
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok

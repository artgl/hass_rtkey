import voluptuous as vol

DOMAIN = "rtkey"
CONF_TOKEN = "token"
CONF_CAMERA_IMAGE_REFRESH_INTERVAL = "camera_image_refresh_interval"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Required(CONF_CAMERA_IMAGE_REFRESH_INTERVAL): int
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

def setup(hass, config):
    conf = config[DOMAIN]
    hass.data[DOMAIN] = {
        "token": conf.get(CONF_TOKEN),
        "camera_image_refresh_interval": conf.get(CONF_CAMERA_IMAGE_REFRESH_INTERVAL)
    }
    hass.helpers.discovery.load_platform('image', DOMAIN, {}, config)

    return True

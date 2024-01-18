import voluptuous as vol

DOMAIN = "rtkey"
CONF_TOKEN = "token"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_TOKEN): str
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

def setup(hass, config):
    conf = config[DOMAIN]
    hass.data[DOMAIN] = {
        "token": conf.get(CONF_TOKEN)
    }
    hass.helpers.discovery.load_platform('image', DOMAIN, {}, config)

    return True

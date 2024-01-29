import logging
import voluptuous as vol

from homeassistant import config_entries

from . import DOMAIN, _LOGGER, DATA_SCHEMA

class RTKeyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, data):
        if data is not None:
            _LOGGER.info(["async_step_user", data])
            return self.async_create_entry(title=data["name"], data=data)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA
        )

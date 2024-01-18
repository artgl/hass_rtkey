import logging
import requests
import functools

from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.components.generic.camera import GenericCamera

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from . import DOMAIN
_LOGGER = logging.getLogger(DOMAIN)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor platform."""
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    config = dict(
      limit_refetch_to_url_change =  False,
      still_image_url = "https://media-vdk4.camera.rt.ru/image/large/8f3a52fc-aa67-48f6-aeaa-fb1379e2c8f5/{{ now() | as_timestamp() | int}}.jpg?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiIsImtpZCI6ImRlZmF1bHRfcHJvZHVjdGlvbiJ9.eyJpc3MiOiJ2Y2Zyb250X3Byb2R1Y3Rpb24iLCJleHAiOjE3MDU1NDMyMDAsInN1YiI6MTcyMjk2MCwiaXAiOiIxMC43OC4zMy4yIiwiY2hhbm5lbCI6IjhmM2E1MmZjLWFhNjctNDhmNi1hZWFhLWZiMTM3OWUyYzhmNSJ9.9oEoQi3Ilm2gnkCGEEemNAvzpXCMwa_gUFjNUFwvdRY",
      framerate = 0.1,
      content_type = None,
      verify_ssl = False,
    )

    add_entities([
      RTKeyCamera(hass, config, 1, 'Camera1'),
    ])


    _LOGGER.error("Added camera entities")

class RTKeyCamera(GenericCamera):
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        url = self._still_image_url.async_render(parse_result=False)
        _LOGGER.error("Fetching {url}".format(url=url));
        r = await self.hass.async_add_executor_job(functools.partial(
            requests.get,
            url,
            allow_redirects=True,
            headers={'X-UTOKEN': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiIsImtpZCI6ImRlZmF1bHRfcHJvZHVjdGlvbiJ9.eyJzdWIiOjE3MjI5NjB9.6lFRjON3NZlVYB_tkL0ioG4SIZe_1c6NdHv0vo9nDrQ'}
        ))
        return r.content

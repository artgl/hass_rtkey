import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from . import RTKeyCamerasApi, DOMAIN, _LOGGER


async def async_setup_entry(hass, config_entry, async_add_entities):
    cameras_api = hass.data[config_entry.entry_id]["cameras_api"]
    cameras_info = await cameras_api.get_cameras_info()
    entities = []
    for camera_info in cameras_info["data"]["items"]:
        entities.append(RTKeyCamera(hass, config_entry, cameras_api, camera_info))
    async_add_entities(entities)

class RTKeyCamera(Camera):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        cameras_api: RTKeyCamerasApi,
        camera_info: dict
    ) -> None:

        super().__init__()

        self.hass = hass
        self.config_entry_id = config_entry.entry_id
        self.cameras_api = cameras_api
        self.camera_id = camera_info["id"]
        self.device_name = cameras_api.build_device_name(camera_info["title"])
        self.entity_id = DOMAIN + "." + re.sub("[^a-zA-z0-9]+", "_", self.device_name).rstrip("_").lower()
        self._attr_unique_id = f"camera-{self.entity_id}"
        self._attr_name = self.device_name
        self._attr_supported_features = CameraEntityFeature.STREAM

    async def stream_source(self) -> str | None:
        _LOGGER.info(f"stream_source")
        url = await self.cameras_api.get_camera_stream_url(self.camera_id)
        _LOGGER.info(f"Camera {self.camera_id} url is {url}")
        return url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        return await self.cameras_api.get_camera_image(self.camera_id)

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, f"{self.config_entry_id}_{self.camera_id}")},
            "name": self.device_name,
        }

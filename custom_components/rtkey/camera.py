import logging
import time
import json
from transliterate import translit
import re
import asyncio
from urllib.parse import urlparse
from aiohttp import web
from haffmpeg.camera import CameraMjpeg
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components import ffmpeg

from . import RTKeyCamerasApi, DOMAIN, _LOGGER, CONF_NAME

async def async_setup_entry(hass, config_entry, async_add_entities):
    cameras_api = RTKeyCamerasApi(hass, config_entry)

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
        self.config_entry_name = config_entry.data[CONF_NAME]
        self.cameras_api = cameras_api
        self.camera_id = camera_info["id"]
        self.camera_name = cameras_api.get_camera_name(camera_info)
        self.camera_netloc = urlparse(camera_info["streamer_url"]).netloc
        self.entity_name = self.camera_name
        self.entity_id = DOMAIN + "." + re.sub("[^a-zA-z0-9]+", "_", self.entity_name).rstrip("_").lower()

        self._attr_unique_id = f"camera-{self.entity_id}"
        self._attr_name = self.entity_name
        self._attr_supported_features = CameraEntityFeature.STREAM

        self._manager = hass.data[ffmpeg.DATA_FFMPEG]
        self._is_on = True

    async def stream_source(self) -> str | None:
        _LOGGER.info(f"stream_source")
        camera_info = await self.cameras_api.get_camera_info(self.camera_id)
        camera_token = camera_info["streamer_token"]
        url = f"https://{self.camera_netloc}/stream/{self.camera_id}/live.mp4?mp4-fragment-length=0.5&mp4-use-speed=0&mp4-afiller=1&token={camera_token}"
        _LOGGER.info(f"Camera {self.camera_id} url is {url}")
        return url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        stream_source = await self.stream_source()
        if not stream_source:
            return None
        return await ffmpeg.async_get_image(
            self.hass,
            stream_source,
            width=width,
            height=height,
        )

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, f"{self.config_entry_id}_{self.camera_id}")},
            "name": self.camera_name,
        }

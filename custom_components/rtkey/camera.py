import re
import datetime

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from . import _LOGGER, DOMAIN, RTKeyCamerasApi, TOKEN_REFRESH_BUFFER


async def async_setup_entry(hass, config_entry, async_add_entities):
    cameras_api = hass.data[config_entry.entry_id]["cameras_api"]
    cameras_info = await cameras_api.get_cameras_info()
    entities = [
        RTKeyCamera(hass, config_entry, cameras_api, camera_info)
        for camera_info in cameras_info["data"]["items"]
    ]
    async_add_entities(entities)


class RTKeyCamera(Camera):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        cameras_api: RTKeyCamerasApi,
        camera_info: dict,
    ) -> None:
        super().__init__()

        self.hass = hass
        self.config_entry_id = config_entry.entry_id
        self.cameras_api = cameras_api
        self.camera_id = camera_info["id"]
        self.device_name = cameras_api.build_device_name(camera_info["title"])
        self.entity_id = (
            DOMAIN
            + "."
            + re.sub("[^a-zA-z0-9]+", "_", self.device_name).rstrip("_").lower()
        )

        self._attr_unique_id = f"camera-{self.entity_id}"
        self._attr_name = self.device_name
        self._attr_supported_features = CameraEntityFeature.STREAM

        # XXX: initially I've used async_track_point_in_utc_time to update stream url exactly before
        # the moment when its token expires, but this worked incorrectly when homeassistant container was paused and then resumed
        self._stream_refresh_cancel_fn = async_track_time_interval(
            self.hass,
            self._stream_refresh,
            datetime.timedelta(seconds=TOKEN_REFRESH_BUFFER),
        )

    async def _stream_refresh(self, now: datetime.datetime) -> None:
        _LOGGER.info(
            "Checking if stream url should be updated for camera %s", self.camera_id
        )
        url = await self.stream_source()
        if self.stream and self.stream.source != url:
            _LOGGER.info("Updating camera %s stream source to %s", self.camera_id, url)
            self.stream.update_source(url)

    async def async_will_remove_from_hass(self) -> None:
        if self._stream_refresh_cancel_fn:
            self._stream_refresh_cancel_fn()

    async def stream_source(self) -> str | None:
        url = await self.cameras_api.get_camera_stream_url(self.camera_id)
        _LOGGER.info("Camera %s stream source is %s", self.camera_id, url)
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

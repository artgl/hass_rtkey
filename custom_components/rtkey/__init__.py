import asyncio
import functools
import json
import logging
import time
from urllib.parse import urlparse

import jwt
import requests
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from transliterate import translit

DOMAIN = "rtkey"

PLATFORMS: list[str] = [Platform.IMAGE, Platform.CAMERA, Platform.SWITCH]

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

TOKEN_REFRESH_REMAINING_TTL = 300


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    _LOGGER.info(["async_setup_entry", config_entry.data, config_entry.options])
    hass.data[config_entry.entry_id] = {
        "cameras_api": RTKeyCamerasApi(hass, config_entry)
    }
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    res = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if res:
        del hass.data[config_entry.entry_id]
    return res

class RTKeyCamerasApi:
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry
    ) -> None:
        self.hass = hass
        self.token = config_entry.options[CONF_TOKEN]
        self.config_entry_name = config_entry.data[CONF_NAME]
        self.lock = asyncio.Lock()
        self.cached_cameras_info = None
        self.cached_camera_images = {}
        self.cached_intercoms_info = None
        self.camera_image_locks = {}
        self.camera_image_tasks = {}
        self.camera_image_refresh_interval = config_entry.options[CONF_CAMERA_IMAGE_REFRESH_INTERVAL]


    async def get_cameras_info(self) -> dict:
        async with self.lock:
            if self.cached_cameras_info:
                _LOGGER.info("Using cached cameras info")
                return self.cached_cameras_info

            r = await self.hass.async_add_executor_job(functools.partial(
                requests.get,
                "https://vc.key.rt.ru/api/v1/cameras?limit=100&offset=0",
                headers={"Authorization": f"Bearer {self.token}"},
                allow_redirects=True,
            ))
            _LOGGER.info(r)
            _LOGGER.info(r.content)

            self.cached_cameras_info = json.loads(r.content)

            for camera_info in self.cached_cameras_info["data"]["items"]:
                decoded_screenshot_token = jwt.decode(camera_info["screenshot_token"], options={"verify_signature": False})
                camera_info["screenshot_token_exp"] = decoded_screenshot_token["exp"]

                decoded_streamer_token = jwt.decode(camera_info["streamer_token"], options={"verify_signature": False})
                camera_info["streamer_token_exp"] = decoded_streamer_token["exp"]

                self.camera_image_locks[camera_info["id"]] = asyncio.Lock()

            return self.cached_cameras_info

    async def clear_cached_cameras_info(self) -> None:
        async with self.lock:
            self.cached_cameras_info = None

    async def get_camera_info(self, camera_id: str) -> dict | None:
        cameras_info = await self.get_cameras_info()
        for camera_info in cameras_info["data"]["items"]:
            if camera_info["id"] == camera_id:
                return camera_info
        return None

    async def get_camera_image(self, camera_id: str) -> bytes | None:
        camera_info = await self.get_camera_info(camera_id)

        now = int(time.time())
        if camera_info and (camera_info["screenshot_token_exp"] - now) < TOKEN_REFRESH_REMAINING_TTL:
            await self.clear_cached_cameras_info()
            camera_info = await self.get_camera_info(camera_id)

        if not camera_info:
            return None

        async with self.camera_image_locks[camera_id]:
            if camera_id in self.cached_camera_images:
                _LOGGER.info("Using cached image for camera %s", camera_id)
                return self.cached_camera_images[camera_id]

            size = "large"
            url = camera_info["screenshot_url_template"].format(
                timestamp=now,
                size=size,
                cdn_token=camera_info["screenshot_token"]
            )
            _LOGGER.info("Fetching %s", url)
            r = await self.hass.async_add_executor_job(functools.partial(
                requests.get,
                url,
                allow_redirects=True,
                headers={"X-UTOKEN": camera_info["user_token"]}
            ))
            _LOGGER.info(r)

            self.cached_camera_images[camera_id] = r.content
            self.camera_image_tasks[camera_id] = asyncio.create_task(self.clear_cached_camera_image(camera_id, self.camera_image_refresh_interval))

            return r.content

    async def get_camera_stream_url(self, camera_id: str) -> str | None:
        camera_info = await self.get_camera_info(camera_id)

        now = int(time.time())
        if camera_info and (camera_info["streamer_token_exp"] - now) < TOKEN_REFRESH_REMAINING_TTL:
            await self.clear_cached_cameras_info()
            camera_info = await self.get_camera_info(camera_id)

        if not camera_info:
            return None

        camera_netloc = urlparse(camera_info["streamer_url"]).netloc
        streamer_token = camera_info["streamer_token"]
        return f"https://{camera_netloc}/stream/{camera_id}/live.mp4?mp4-fragment-length=0.5&mp4-use-speed=0&mp4-afiller=1&token={streamer_token}"

    async def clear_cached_camera_image(self, camera_id: str, ttl: int) -> None:
        await asyncio.sleep(ttl)
        async with self.camera_image_locks[camera_id]:
            del self.cached_camera_images[camera_id]
        _LOGGER.info("Deleted cached image for camera %s", camera_id)

    def build_device_name(self, device_title) -> str:
        device_name = device_title.lower()
        device_name = f"{self.config_entry_name} {device_name}"
        device_name = translit(device_name, "ru", reversed=True)
        return device_name.capitalize()

    async def get_intercoms_info(self) -> dict:
        async with self.lock:
            if self.cached_intercoms_info:
                _LOGGER.info("Using cached intercoms info")
                return self.cached_intercoms_info

            r = await self.hass.async_add_executor_job(functools.partial(
                requests.get,
                "https://household.key.rt.ru/api/v2/app/devices/intercom",
                headers={"Authorization": f"Bearer {self.token}"},
                allow_redirects=True,
            ))
            _LOGGER.info(r)
            _LOGGER.info(r.content)

            self.cached_intercoms_info = json.loads(r.content)

            return self.cached_intercoms_info

    async def open_intercom(self, intercom_id) -> None:
        async with self.lock:
            url = f"https://household.key.rt.ru/api/v2/app/devices/{intercom_id}/open"
            _LOGGER.info("Fetching %s", url)
            r = await self.hass.async_add_executor_job(functools.partial(
                requests.post,
                url,
                allow_redirects=True,
                headers={"Authorization": f"Bearer {self.token}"},
            ))
            _LOGGER.info(r)

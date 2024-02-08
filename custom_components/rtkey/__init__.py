import voluptuous as vol
import logging
import json
import asyncio
import functools
import jwt
import requests
from transliterate import translit
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

DOMAIN = "rtkey"

PLATFORMS: list[str] = [Platform.IMAGE, Platform.CAMERA]

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
    _LOGGER.info(["async_setup_entry", config_entry.data, config_entry.options])
    hass.data[config_entry.entry_id] = {
        "cameras_api": RTKeyCamerasApi(hass, config_entry)
    }
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    res = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if res:
        del hass.data[config_entry.entity_id]
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
        self.camera_image_locks = {}
        self.cached_cameras_info = None
        self.cached_camera_images = {}
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

    async def get_camera_image(self, camera_id: str) -> bytes | None:
        camera_info = await self.get_camera_info(camera_id)

        now = int(time.time())
        if camera_info and (camera_info["screenshot_token_exp"] - now) < 300:
            await self.clear_cached_cameras_info()
            camera_info = await self.get_camera_info(camera_id)

        if camera_info:
            async with self.camera_image_locks[camera_id]:
                if camera_id in self.cached_camera_images:
                    _LOGGER.info(f"Using cached image for camera {camera_id}");
                    return self.cached_camera_images[camera_id]

                size = "large"
                url = camera_info["screenshot_url_template"].format(
                    timestamp=now,
                    size=size,
                    cdn_token=camera_info["screenshot_token"]
                )
                _LOGGER.info(f"Fetching {url}");
                r = await self.hass.async_add_executor_job(functools.partial(
                    requests.get,
                    url,
                    allow_redirects=True,
                    headers={"X-UTOKEN": camera_info["user_token"]}
                ))
                _LOGGER.info(r);

                self.cached_camera_images[camera_id] = r.content
                self.camera_image_tasks[camera_id] = asyncio.create_task(self.clear_cached_camera_image(camera_id, self.camera_image_refresh_interval))

                return r.content

    async def clear_cached_camera_image(self, camera_id: str, ttl: int) -> None:
        await asyncio.sleep(ttl)
        async with self.camera_image_locks[camera_id]:
            del self.cached_camera_images[camera_id]
        _LOGGER.info(f"Deleted cached image for camera {camera_id}");

    def get_camera_name(self, camera_info: dict) -> str:
        camera_name = camera_info["title"].lower()
        camera_name = f"{self.config_entry_name} {camera_name}"
        camera_name = translit(camera_name, "ru", reversed=True)
        camera_name = camera_name.capitalize()
        return camera_name

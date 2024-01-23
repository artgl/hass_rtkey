import logging
import requests
import functools
import time
from datetime import datetime
import json
from transliterate import translit
import re
import jwt
import asyncio

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.core import ServiceCall

from . import DOMAIN
_LOGGER = logging.getLogger(DOMAIN)
_LOGGER.setLevel(logging.INFO)

class RTKeyCamerasApi:
    def __init__(
        self,
        hass: HomeAssistant
    ) -> None:
        self.hass = hass
        self.token = hass.data[DOMAIN]["token"]
        self.lock = asyncio.Lock()
        self.camera_image_locks = {}
        self.cached_cameras_info = None
        self.cached_camera_images = {}
        self.camera_image_tasks = {}
        self.camera_image_refresh_interval = hass.data[DOMAIN]["camera_image_refresh_interval"]

    async def get_cameras_info(self) -> dict:
        async with self.lock:
            if self.cached_cameras_info:
                _LOGGER.info("Using cached cameras info")
                return self.cached_cameras_info

            r = await self.hass.async_add_executor_job(functools.partial(
                requests.get,
                "https://vc.key.rt.ru/api/v1/cameras?limit=100&offset=0",
                headers={'Authorization': 'Bearer {token}'.format(token=self.token)},
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
                    _LOGGER.info("Using cached image for camera {camera_id}".format(camera_id=camera_id));
                    return self.cached_camera_images[camera_id]

                size = 'large'
                url = camera_info["screenshot_url_template"].format(
                    timestamp=now,
                    size=size,
                    cdn_token=camera_info["screenshot_token"]
                )
                _LOGGER.info("Fetching {url}".format(url=url));
                r = await self.hass.async_add_executor_job(functools.partial(
                    requests.get,
                    url,
                    allow_redirects=True,
                    headers={'X-UTOKEN': camera_info["user_token"]}
                ))
                _LOGGER.info(r);

                self.cached_camera_images[camera_id] = r.content
                self.camera_image_tasks[camera_id] = asyncio.create_task(self.clear_cached_camera_image(camera_id, self.camera_image_refresh_interval))

                return r.content

    async def clear_cached_camera_image(self, camera_id: str, ttl: int) -> None:
        await asyncio.sleep(ttl)
        async with self.camera_image_locks[camera_id]:
            del self.cached_camera_images[camera_id]
        _LOGGER.info("Deleted cached image for camera {camera_id}".format(camera_id=camera_id));

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    _LOGGER.info("Retrieving info about available cameras");

    cameras_api = RTKeyCamerasApi(hass)

    cameras_info = await cameras_api.get_cameras_info()

    entities = []
    for camera_info in cameras_info["data"]["items"]:
        camera_id = camera_info["id"]
        name = translit(camera_info["title"], "ru", reversed=True)
        name2 = re.sub("[^a-zA-z0-9]+", "_", name).rstrip("_").lower()
        entity_id = "image.{domain}_{camera_name}".format(domain=DOMAIN,camera_name=name2)
        entities.append(RTKeyCameraImageEntity(hass, cameras_api, camera_id, name, entity_id))
    add_entities(entities)

class RTKeyCameraImageEntity(ImageEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        cameras_api: RTKeyCamerasApi,
        camera_id: str,
        name: str,
        entity_id: str
    ) -> None:
        self.hass = hass
        self.cameras_api = cameras_api
        self.camera_id = camera_id
        self.name = name
        self.entity_id = entity_id
        self.camera_image_refresh_interval = hass.data[DOMAIN]["camera_image_refresh_interval"]
        super().__init__(hass)

    async def async_image(self) -> bytes | None:
        res = await self.cameras_api.get_camera_image(self.camera_id)
        self.camera_image_task = asyncio.create_task(self.set_image_last_updated(self.camera_image_refresh_interval))
        return res

    async def set_image_last_updated(self, ttl: int) -> None:
        await asyncio.sleep(ttl)
        self._attr_image_last_updated = datetime.now()
        await self.hass.services.async_call("homeassistant", "update_entity", {"entity_id": self.entity_id}, blocking=False)

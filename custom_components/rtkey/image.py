import logging
import requests
import functools
import time
import json
from transliterate import translit
import re

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN
_LOGGER = logging.getLogger(DOMAIN)
_LOGGER.setLevel(logging.INFO)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    _LOGGER.info("Retrieving info about available cameras");

    r = await hass.async_add_executor_job(functools.partial(
        requests.get,
        "https://vc.key.rt.ru/api/v1/cameras?limit=100&offset=0",
        headers={'Authorization': 'Bearer {token}'.format(token=hass.data[DOMAIN]["token"])},
        allow_redirects=True,
    ))

    _LOGGER.info(r)

    r = json.loads(r.content)

    entities = []

    for item in r["data"]["items"]:
        name = translit(item["title"], "ru", reversed=True)
        url_template = item["screenshot_url_template"]
        cdn_token = item["screenshot_token"]
        user_token = item["user_token"]
        _LOGGER.info([name, url_template, cdn_token, user_token])
        entities.append(RTKeyImageEntity(hass, name, url_template, cdn_token, user_token))
        break

    add_entities(entities)

class RTKeyImageEntity(ImageEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        url_template: str,
        cdn_token: str,
        user_token: str,
    ) -> None:
      entity_id = re.sub("[^a-zA-z0-9]+", "_", name).rstrip("_").lower()
      self.entity_id = "image.{domain}_{entity_id}".format(domain=DOMAIN,entity_id=entity_id)
      self.name = name
      self.url_template = url_template
      self.cdn_token = cdn_token
      self.user_token = user_token
      super().__init__(hass)

    async def async_image(
        self
    ) -> bytes | None:
        size = 'large'
        url = self.url_template.format(
            timestamp=int(time.time()),
            size=size,
            cdn_token=self.cdn_token
        )
        _LOGGER.info("Fetching {url}".format(url=url));
        r = await self.hass.async_add_executor_job(functools.partial(
            requests.get,
            url,
            allow_redirects=True,
            headers={'X-UTOKEN': self.user_token}
        ))
        _LOGGER.info(r);
        return r.content

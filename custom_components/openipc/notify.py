"""Notification service for OpenIPC cameras."""
import voluptuous as vol
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_EXTRA,
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
)
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    BaseNotificationService,
    PLATFORM_SCHEMA,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.template import Template

from .const import DOMAIN

# Схема для платформы уведомлений
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional("name"): cv.string,
        vol.Required("entity_id"): cv.entity_ids,
        vol.Optional("language", default="ru"): vol.In(["ru", "en"]),
        vol.Optional("volume", default=70): vol.All(vol.Coerce(int), vol.Range(0, 100)),
    }
)


async def async_get_service(hass, config, discovery_info=None):
    """Get the OpenIPC notification service."""
    await async_setup_reload_service(hass, DOMAIN, ["notify"])
    
    entity_ids = config.get("entity_id")
    language = config.get("language", "ru")
    volume = config.get("volume", 70)
    
    return OpenIPCNotificationService(hass, entity_ids, language, volume)


class OpenIPCNotificationService(BaseNotificationService):
    """Implement the notification service for OpenIPC cameras."""

    def __init__(self, hass, entity_ids, language="ru", volume=70):
        """Initialize the service."""
        self.hass = hass
        self.entity_ids = entity_ids
        self.language = language
        self.volume = volume

    async def async_send_message(self, message: str, **kwargs):
        """Send a TTS message to the camera speaker."""
        data = kwargs.get(ATTR_DATA, {})
        
        # Определяем язык (из данных или из настроек)
        language = data.get("language", self.language)
        
        # Определяем громкость (из данных или из настроек)
        volume = data.get("volume", self.volume)
        
        # Определяем entity_id (из данных или из настроек)
        entity_id = data.get(ATTR_ENTITY_ID, self.entity_ids)
        if isinstance(entity_id, list):
            if len(entity_id) == 1:
                entity_id = entity_id[0]
        
        # Сначала устанавливаем громкость
        await self.hass.services.async_call(
            "media_player",
            "volume_set",
            {
                "entity_id": entity_id,
                "volume_level": volume / 100,
            },
            blocking=True
        )
        
        # Воспроизводим TTS
        service_data = {
            "entity_id": entity_id,
            "media_content_type": "tts",
            "media_content_id": message,
        }
        
        # Добавляем язык в extra если нужно
        if language != "ru":
            service_data["extra"] = {"language": language}
        
        await self.hass.services.async_call(
            "media_player",
            "play_media",
            service_data,
            blocking=True
        )
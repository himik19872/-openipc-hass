"""Media player platform for OpenIPC - ULTRA SIMPLE VERSION."""
import logging
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from .const import DOMAIN, CONF_DEVICE_TYPE, DEVICE_TYPE_BEWARD

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC media players."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_BEWARD and coordinator.beward:
        async_add_entities([BewardAudioPlayer(coordinator, entry)])

class BewardAudioPlayer(MediaPlayerEntity):
    """Ultra simple media player."""

    def __init__(self, coordinator, entry):
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} Audio"
        self._attr_unique_id = f"{entry.entry_id}_audio"
        self._attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA
        self._attr_state = MediaPlayerState.IDLE

    async def async_play_media(self, media_type, media_id, **kwargs):
        if not self.coordinator.beward:
            return

        # Запускаем скрипт для TTS
        if "tts/google_translate" in media_id:
            _LOGGER.info("🔊 Запуск TTS через скрипт")
            await self.hass.services.async_call(
                "script",
                "beward_say",
                {"message": "тест"},  # В реальности нужно парсить сообщение
                blocking=False
            )
            return

        # Встроенные звуки (оставляем как есть)
        sound_map = {
            "beep": self.coordinator.beward.async_play_beep,
            "ding": self.coordinator.beward.async_play_ding,
            "doorbell": self.coordinator.beward.async_play_doorbell,
        }
        if media_id in sound_map:
            await sound_map[media_id]()
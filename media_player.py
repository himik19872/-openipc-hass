"""Media player platform for OpenIPC."""
import logging
import os
import tempfile
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_DEVICE_TYPE, DEVICE_TYPE_BEWARD, DEVICE_TYPE_OPENIPC

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC media players."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE)
    
    entities = []
    
    # Для Beward
    if device_type == DEVICE_TYPE_BEWARD and coordinator.beward:
        entities.append(BewardAudioPlayer(coordinator, entry))
    
    # Для OpenIPC
    elif device_type == DEVICE_TYPE_OPENIPC and coordinator.openipc_audio:
        entities.append(OpenIPCAudioPlayer(coordinator, entry))
    
    if entities:
        async_add_entities(entities)


class OpenIPCAudioPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for OpenIPC cameras with TTS support."""

    def __init__(self, coordinator, entry):
        """Initialize the media player."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get(CONF_NAME, 'OpenIPC')} Audio"
        self._attr_unique_id = f"{entry.entry_id}_audio"
        self._attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA
        self._attr_state = MediaPlayerState.IDLE
        self._attr_icon = "mdi:speaker"

    async def async_play_media(self, media_type, media_id, **kwargs):
        """
        Play media.
        media_type: "tts" or "file"
        media_id: text for TTS or path to PCM file
        """
        _LOGGER.info("🔊 OpenIPC play_media: type=%s, id=%s", media_type, media_id)
        
        if not self.coordinator.openipc_audio:
            _LOGGER.error("OpenIPC audio not available")
            return

        if media_type == "tts":
            # Воспроизводим текст через TTS
            language = kwargs.get("language", "ru")
            self._attr_state = MediaPlayerState.PLAYING
            self.async_write_ha_state()
            
            success = await self.coordinator.openipc_audio.async_generate_and_play_tts(
                media_id, language
            )
            
            self._attr_state = MediaPlayerState.IDLE
            self.async_write_ha_state()
            
            if success:
                _LOGGER.info("✅ TTS played successfully")
            else:
                _LOGGER.error("❌ TTS playback failed")
                
        elif media_type == "file":
            # Воспроизводим готовый PCM файл
            if not os.path.exists(media_id):
                _LOGGER.error("File not found: %s", media_id)
                return
            
            self._attr_state = MediaPlayerState.PLAYING
            self.async_write_ha_state()
            
            success = await self.coordinator.openipc_audio.async_play_pcm(media_id)
            
            self._attr_state = MediaPlayerState.IDLE
            self.async_write_ha_state()
            
            if success:
                _LOGGER.info("✅ PCM file played successfully")
            else:
                _LOGGER.error("❌ PCM playback failed")

    @property
    def device_info(self):
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {})
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get(CONF_NAME, "OpenIPC Camera"),
            "manufacturer": "OpenIPC",
            "model": parsed.get("model", "Camera"),
            "sw_version": parsed.get("firmware", "Unknown"),
        }


class BewardAudioPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for Beward cameras (existing implementation)."""

    def __init__(self, coordinator, entry):
        """Initialize the media player."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get(CONF_NAME, 'Beward')} Audio"
        self._attr_unique_id = f"{entry.entry_id}_audio"
        self._attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA
        self._attr_state = MediaPlayerState.IDLE
        self._attr_icon = "mdi:speaker"

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play audio on Beward camera."""
        if not self.coordinator.beward:
            _LOGGER.error("Beward device not available")
            return

        # TTS для Beward
        if media_type == "tts":
            _LOGGER.info("🔊 Beward TTS: %s", media_id)
            language = kwargs.get("language", "ru")
            
            self._attr_state = MediaPlayerState.PLAYING
            self.async_write_ha_state()
            
            # Используем shell_command для TTS (как настроено ранее)
            await self.hass.services.async_call(
                "shell_command",
                "beward_say",
                {"message": media_id, "language": language},
                blocking=True
            )
            
            self._attr_state = MediaPlayerState.IDLE
            self.async_write_ha_state()
            
        # Встроенные звуки
        elif media_id in ["beep", "ding", "doorbell"]:
            sound_map = {
                "beep": self.coordinator.beward.async_play_beep,
                "ding": self.coordinator.beward.async_play_ding,
                "doorbell": self.coordinator.beward.async_play_doorbell,
            }
            await sound_map[media_id]()

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get(CONF_NAME, "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }
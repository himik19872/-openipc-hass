"""Media player platform for OpenIPC cameras with TTS support."""
import logging
import os
import aiohttp
import voluptuous as vol
from typing import Optional

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import (
    STATE_IDLE,
    STATE_PLAYING,
    STATE_OFF,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .const import DOMAIN, CONF_DEVICE_TYPE, DEVICE_TYPE_BEWARD, DEVICE_TYPE_OPENIPC

_LOGGER = logging.getLogger(__name__)

# Поддерживаемые функции
SUPPORT_OPENIPC = (
    MediaPlayerEntityFeature.PLAY_MEDIA |
    MediaPlayerEntityFeature.VOLUME_SET |
    MediaPlayerEntityFeature.VOLUME_STEP |
    MediaPlayerEntityFeature.STOP |
    MediaPlayerEntityFeature.TURN_ON |
    MediaPlayerEntityFeature.TURN_OFF
)

SUPPORT_BEWARD = SUPPORT_OPENIPC

# URL аддона
ADDON_URL = "http://localhost:5000"

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC media players."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_OPENIPC)
    
    entities = []
    
    if device_type == DEVICE_TYPE_BEWARD:
        entities.append(BewardMediaPlayer(coordinator, entry))
    else:
        entities.append(OpenIPCMediaPlayer(coordinator, entry))
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info(f"✅ Added media player for {entry.data.get('name')}")
        
        # Регистрируем сервисы после добавления entities
        await async_register_services(hass)


async def async_register_services(hass):
    """Register custom services."""
    
    # Проверяем, зарегистрированы ли уже сервисы
    if hass.services.has_service(DOMAIN, "play_tts"):
        return
    
    async def async_play_tts(call):
        """Play TTS on media player."""
        entity_id = call.data.get('entity_id')
        message = call.data.get('message')
        language = call.data.get('language', 'ru')
        volume = call.data.get('volume', 50)
        
        _LOGGER.info(f"TTS service called: {entity_id} - '{message}'")
        
        if not entity_id:
            _LOGGER.error("No entity_id provided")
            return
        
        if not message:
            _LOGGER.error("No message provided")
            return
        
        # Находим entity через hass
        entity_state = hass.states.get(entity_id)
        if not entity_state:
            _LOGGER.error(f"Entity {entity_id} not found")
            return
        
        # Ищем существующий media_player entity через платформу
        media_player_entity = None
        if 'entity_components' in hass.data and 'media_player' in hass.data['entity_components']:
            for entity in hass.data['entity_components']['media_player'].entities:
                if entity.entity_id == entity_id:
                    media_player_entity = entity
                    _LOGGER.info(f"Found existing media player entity: {entity_id}")
                    break
        
        if not media_player_entity:
            _LOGGER.error(f"Could not find media player entity: {entity_id}")
            return
        
        # Отправляем событие о начале TTS
        async_dispatcher_send(hass, f"{entity_id}-tts_start", message)
        
        # Устанавливаем громкость
        _LOGGER.info(f"Setting volume to {volume/100}")
        await media_player_entity.async_set_volume_level(volume / 100)
        
        # Воспроизводим TTS
        _LOGGER.info(f"Playing TTS: '{message}'")
        await media_player_entity.async_play_media("tts", message, language=language)
        
        # Отправляем событие о завершении TTS
        async_dispatcher_send(hass, f"{entity_id}-tts_end", message)
        
        _LOGGER.info(f"✅ TTS played on {entity_id}")
    
    # Регистрируем сервис
    hass.services.async_register(
        DOMAIN, 
        "play_tts", 
        async_play_tts,
        schema=vol.Schema({
            vol.Required('entity_id'): cv.entity_id,
            vol.Required('message'): cv.string,
            vol.Optional('language', default='ru'): vol.In(['ru', 'en']),
            vol.Optional('volume', default=50): vol.All(vol.Coerce(int), vol.Range(0, 100)),
        })
    )
    
    _LOGGER.info("✅ Registered play_tts service")


class OpenIPCMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for OpenIPC cameras."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_icon = "mdi:speaker"

    def __init__(self, coordinator, entry):
        """Initialize the media player."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get(CONF_NAME, 'OpenIPC')} Speaker"
        self._attr_unique_id = f"{entry.entry_id}_speaker"
        self._attr_supported_features = SUPPORT_OPENIPC
        self._attr_state = MediaPlayerState.IDLE
        self._attr_volume_level = 0.5
        self._attr_media_content_type = "audio/mpeg"
        
        self._is_on = True
        self._media_title = None
        self._media_duration = None
        self._media_position = None
        self._media_position_updated_at = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.data.get(CONF_NAME, "OpenIPC Camera"),
            manufacturer="OpenIPC",
            model=parsed.get("model", "Camera"),
            sw_version=parsed.get("firmware", "Unknown"),
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._is_on

    @property
    def media_title(self) -> Optional[str]:
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_duration(self) -> Optional[int]:
        """Return the duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self) -> Optional[int]:
        """Return the position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self) -> Optional[str]:
        """Return the time when the position was last updated."""
        return self._media_position_updated_at

    async def async_turn_on(self):
        """Turn the media player on."""
        self._is_on = True
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        self._is_on = False
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs):
        """Play media (TTS or audio file)."""
        _LOGGER.info(f"OpenIPC play_media: type={media_type}, id={media_id}, kwargs={kwargs}")
        
        if not self._is_on:
            await self.async_turn_on()
        
        self._attr_state = MediaPlayerState.PLAYING
        
        # Определяем язык из kwargs или параметров
        language = kwargs.get("language", "ru")
        
        if media_type == "tts":
            self._media_title = f"TTS: {media_id[:50]}"
        else:
            self._media_title = media_id
            
        self.async_write_ha_state()
        
        try:
            # Используем addon
            camera_ip = self.entry.data.get(CONF_HOST)
            _LOGGER.info(f"Using addon for TTS to {camera_ip}")
            
            # Прямой HTTP запрос к аддону
            url = f"{ADDON_URL}/api/tts"
            payload = {
                "camera_id": camera_ip,
                "text": media_id,
                "lang": language
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            _LOGGER.info("✅ TTS sent via addon")
                        else:
                            _LOGGER.error(f"❌ TTS via addon failed: {data}")
                            # Просто логируем ошибку, без fallback
                    else:
                        _LOGGER.error(f"❌ HTTP {response.status}")
                        
        except Exception as err:
            _LOGGER.error(f"TTS error: {err}")
        
        # Устанавливаем примерную длительность (1 секунда на 10 символов)
        self._media_duration = max(5, len(media_id) // 10)
        self._media_position = 0
        self._media_position_updated_at = dt_util.utcnow()
        
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_stop(self):
        """Stop playback."""
        _LOGGER.info("OpenIPC stop")
        self._attr_state = MediaPlayerState.IDLE
        self._media_title = None
        self._media_duration = None
        self._media_position = None
        self._media_position_updated_at = None
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float):
        """Set volume level."""
        _LOGGER.info(f"OpenIPC set volume: {volume}")
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Turn volume up."""
        new_volume = min(1.0, self._attr_volume_level + 0.1)
        await self.async_set_volume_level(new_volume)

    async def async_volume_down(self):
        """Turn volume down."""
        new_volume = max(0.0, self._attr_volume_level - 0.1)
        await self.async_set_volume_level(new_volume)


class BewardMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for Beward cameras."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_icon = "mdi:speaker"

    def __init__(self, coordinator, entry):
        """Initialize the media player."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get(CONF_NAME, 'Beward')} Speaker"
        self._attr_unique_id = f"{entry.entry_id}_speaker"
        self._attr_supported_features = SUPPORT_BEWARD
        self._attr_state = MediaPlayerState.IDLE
        self._attr_volume_level = 0.5
        self._attr_media_content_type = "audio/G.711A"
        
        self._is_on = True
        self._media_title = None
        self._media_duration = None
        self._media_position = None
        self._media_position_updated_at = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.data.get(CONF_NAME, "Beward Doorbell"),
            manufacturer="Beward",
            model="DS07P-LP",
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._is_on

    @property
    def media_title(self) -> Optional[str]:
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_duration(self) -> Optional[int]:
        """Return the duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self) -> Optional[int]:
        """Return the position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self) -> Optional[str]:
        """Return the time when the position was last updated."""
        return self._media_position_updated_at

    async def async_turn_on(self):
        """Turn the media player on."""
        self._is_on = True
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        self._is_on = False
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs):
        """Play media (TTS or audio file)."""
        _LOGGER.info(f"Beward play_media: type={media_type}, id={media_id}, kwargs={kwargs}")
        
        if not self._is_on:
            await self.async_turn_on()
        
        self._attr_state = MediaPlayerState.PLAYING
        
        language = kwargs.get("language", "ru")
        
        if media_type == "tts":
            self._media_title = f"TTS: {media_id[:50]}"
        else:
            self._media_title = media_id
            
        self.async_write_ha_state()
        
        try:
            camera_ip = self.entry.data.get(CONF_HOST, '192.168.1.10')
            _LOGGER.info(f"Using addon for Beward TTS to {camera_ip}")
            
            # Прямой HTTP запрос к аддону как в curl
            url = f"{ADDON_URL}/api/tts"
            payload = {
                "camera_id": camera_ip,
                "text": media_id,
                "lang": language
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            _LOGGER.info("✅ Beward TTS sent via addon")
                        else:
                            _LOGGER.error(f"❌ Beward TTS via addon failed: {data}")
                    else:
                        _LOGGER.error(f"❌ HTTP {response.status}")
                        
        except Exception as err:
            _LOGGER.error(f"Beward TTS error: {err}")
        
        self._media_duration = max(5, len(media_id) // 10)
        self._media_position = 0
        self._media_position_updated_at = dt_util.utcnow()
        
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_stop(self):
        """Stop playback."""
        _LOGGER.info("Beward stop")
        self._attr_state = MediaPlayerState.IDLE
        self._media_title = None
        self._media_duration = None
        self._media_position = None
        self._media_position_updated_at = None
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float):
        """Set volume level."""
        _LOGGER.info(f"Beward set volume: {volume}")
        self._attr_volume_level = volume
        
        if self.coordinator.beward:
            volume_percent = int(volume * 100)
            await self.coordinator.beward.async_set_volume(volume_percent)
        
        self.async_write_ha_state()

    async def async_volume_up(self):
        """Turn volume up."""
        new_volume = min(1.0, self._attr_volume_level + 0.1)
        await self.async_set_volume_level(new_volume)

    async def async_volume_down(self):
        """Turn volume down."""
        new_volume = max(0.0, self._attr_volume_level - 0.1)
        await self.async_set_volume_level(new_volume)
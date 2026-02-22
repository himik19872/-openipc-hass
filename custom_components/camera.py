"""Camera platform for OpenIPC."""
import logging
import aiohttp
import asyncio
from homeassistant.components.camera import Camera
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .const import (
    DOMAIN, 
    IMAGE_JPEG, 
    RTSP_STREAM_MAIN, 
    RTSP_STREAM_SUB,
    MJPEG_STREAM,
    MP4_STREAM
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC camera."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Создаем основную камеру
    camera = OpenIPCCamera(coordinator, entry)
    async_add_entities([camera])

class OpenIPCCamera(Camera):
    """Representation of an OpenIPC camera."""

    def __init__(self, coordinator, entry):
        """Initialize the camera."""
        super().__init__()
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = entry.data.get("name", "OpenIPC Camera")
        self._attr_unique_id = entry.entry_id
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
        
        # Выбираем поток в зависимости от настроек
        stream_profile = entry.data.get("stream_profile", "main")
        if stream_profile == "main":
            self._rtsp_path = RTSP_STREAM_MAIN
        else:
            self._rtsp_path = RTSP_STREAM_SUB
        
        # Формируем RTSP URL с аутентификацией
        self._rtsp_url = f"rtsp://{self._username}:{self._password}@{coordinator.host}:{coordinator.rtsp_port}{self._rtsp_path}"
        
        # URL для снимка
        self._snapshot_url = f"http://{coordinator.host}:{coordinator.port}{IMAGE_JPEG}"
        
        # MJPEG URL для альтернативного потока
        self._mjpeg_url = f"http://{coordinator.host}:{coordinator.port}{MJPEG_STREAM}"
        
        # Создаем сессию с аутентификацией
        self._auth = aiohttp.BasicAuth(self._username, self._password)

    @property
    def brand(self):
        """Return the camera brand."""
        return "OpenIPC"

    @property
    def model(self):
        """Return the camera model."""
        parsed = self.coordinator.data.get("parsed", {})
        return parsed.get("model", "Camera")

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return self.coordinator.data.get("motion", {}).get("enabled", False)

    async def stream_source(self):
        """Return the source of the stream."""
        return self._rtsp_url

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        try:
            async with self.coordinator.session.get(
                self._snapshot_url, 
                auth=self._auth,
                timeout=5
            ) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    _LOGGER.debug("Failed to get image: HTTP %s", response.status)
                    return None
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout getting image from %s", self._snapshot_url)
            return None
        except Exception as err:
            _LOGGER.debug("Error getting image: %s", err)
            return None

    async def async_handle_web_rtc_offer(self, offer_sdp: str) -> str | None:
        """Handle the WebRTC offer and return an answer."""
        # Здесь можно добавить поддержку WebRTC если нужно
        return None

    @property
    def device_info(self):
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {})
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "OpenIPC Camera"),
            "manufacturer": "OpenIPC",
            "model": parsed.get("model", "Camera"),
            "sw_version": parsed.get("firmware", "Unknown"),
        }
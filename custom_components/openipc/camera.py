"""Camera platform for OpenIPC integration."""
import logging
import aiohttp
import asyncio
from homeassistant.components.camera import Camera
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, 
    IMAGE_JPEG, 
    RTSP_STREAM_MAIN, 
    RTSP_STREAM_SUB,
    MJPEG_STREAM,
    MP4_STREAM,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_BEWARD,
    DEVICE_TYPE_VIVOTEK,
    DEVICE_TYPE_OPENIPC,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC camera."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_OPENIPC)
    
    if device_type == DEVICE_TYPE_BEWARD:
        camera = BewardCamera(coordinator, entry)
    elif device_type == DEVICE_TYPE_VIVOTEK:
        camera = VivotekCamera(coordinator, entry)
    else:
        camera = OpenIPCCamera(coordinator, entry)
    
    async_add_entities([camera])

class BaseCamera(CoordinatorEntity, Camera):
    """Base representation of a camera."""

    def __init__(self, coordinator, entry):
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = entry.data.get("name", "Camera")
        self._attr_unique_id = entry.entry_id
        self._username = entry.data[CONF_USERNAME]
        self._password = entry.data[CONF_PASSWORD]
        self._auth = aiohttp.BasicAuth(self._username, self._password)
        
    @property
    def device_info(self):
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {}) if self.coordinator.data else {}
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Camera"),
            "manufacturer": parsed.get("manufacturer", self._get_manufacturer()),
            "model": parsed.get("model", self._get_model()),
            "sw_version": parsed.get("firmware", "Unknown"),
        }
    
    def _get_manufacturer(self):
        """Get manufacturer name."""
        return "Unknown"
    
    def _get_model(self):
        """Get model name."""
        return "Camera"


class OpenIPCCamera(BaseCamera):
    """Representation of an OpenIPC camera."""

    def __init__(self, coordinator, entry):
        """Initialize the camera."""
        super().__init__(coordinator, entry)
        
        # Формируем RTSP URL
        stream_profile = entry.data.get("stream_profile", "main")
        if stream_profile == "main":
            self._rtsp_path = RTSP_STREAM_MAIN
        else:
            self._rtsp_path = RTSP_STREAM_SUB
        
        self._rtsp_url = f"rtsp://{self._username}:{self._password}@{coordinator.host}:{coordinator.rtsp_port}{self._rtsp_path}"
        
        # URL для снимка
        self._snapshot_url = f"http://{coordinator.host}:{coordinator.port}{IMAGE_JPEG}"
        
        # MJPEG URL для альтернативного потока
        self._mjpeg_url = f"http://{coordinator.host}:{coordinator.port}{MJPEG_STREAM}"

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

    def _get_manufacturer(self):
        return "OpenIPC"


class BewardCamera(BaseCamera):
    """Representation of a Beward camera."""

    def __init__(self, coordinator, entry):
        """Initialize the camera."""
        super().__init__(coordinator, entry)
        self._beward = coordinator.beward

    @property
    def brand(self):
        """Return the camera brand."""
        return "Beward"

    @property
    def model(self):
        """Return the camera model."""
        return "DS07P-LP"

    async def stream_source(self):
        """Return the source of the stream."""
        if self._beward:
            return self._beward.rtsp_url_main
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self._beward:
            return await self._beward.async_get_snapshot()
        return None

    def _get_manufacturer(self):
        return "Beward"

    def _get_model(self):
        return "DS07P-LP"


class VivotekCamera(BaseCamera):
    """Representation of a Vivotek camera."""

    def __init__(self, coordinator, entry):
        """Initialize the camera."""
        super().__init__(coordinator, entry)
        self._vivotek = coordinator.vivotek

    @property
    def brand(self):
        """Return the camera brand."""
        return "Vivotek"

    @property
    def model(self):
        """Return the camera model."""
        return "SD9364-EHL"

    async def stream_source(self):
        """Return the source of the stream."""
        if self._vivotek:
            return self._vivotek.rtsp_url_main
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        if self._vivotek:
            return await self._vivotek.async_get_snapshot()
        return None

    def _get_manufacturer(self):
        return "Vivotek"

    def _get_model(self):
        return "SD9364-EHL"
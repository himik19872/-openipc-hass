"""ONVIF client for PTZ control and event handling."""
import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

try:
    from onvif import ONVIFCamera
    from onvif.exceptions import ONVIFError
    ONVIF_AVAILABLE = True
except ImportError:
    ONVIF_AVAILABLE = False
    ONVIFCamera = None
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.warning("ONVIF library not available. PTZ disabled. Install: pip install onvif-zeep")

from .const import (
    DEVICE_TYPE_BEWARD,
    DEVICE_TYPE_VIVOTEK,
    DEFAULT_PTZ_SPEED,
)

_LOGGER = logging.getLogger(__name__)

class OpenIPCOnvifClient:
    """ONVIF client for PTZ and event management."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        username: str,
        password: str,
        device_type: str,
        camera_name: str,
    ):
        """Initialize ONVIF client."""
        self.hass = hass
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.device_type = device_type
        self.camera_name = camera_name
        self.session = async_get_clientsession(hass)
        
        self._cam = None
        self._ptz = None
        self._media = None
        self._events = None
        self._profile = None
        self._available = False
        
        # PTZ speed (0.0 to 1.0) [citation:2]
        self._ptz_speed = DEFAULT_PTZ_SPEED
        
        # Presets cache
        self._presets = {}
        
        # Event callbacks
        self._event_callbacks = []
        
        if ONVIF_AVAILABLE:
            _LOGGER.info(f"✅ ONVIF client initialized for {camera_name} at {host}:{port}")
        else:
            _LOGGER.warning(f"⚠️ ONVIF client in simulation mode for {camera_name}")

    async def async_connect(self) -> bool:
        """Connect to camera via ONVIF."""
        if not ONVIF_AVAILABLE:
            self._available = True
            return True

        try:
            # Создаем ONVIF клиент в executor
            self._cam = await self.hass.async_add_executor_job(
                lambda: ONVIFCamera(
                    self.host,
                    self.port,
                    self.username,
                    self.password,
                    "/etc/onvif/wsdl"  # Путь к WSDL файлам
                )
            )

            # Получаем сервисы
            self._media = await self.hass.async_add_executor_job(
                self._cam.create_media_service
            )
            
            # Получаем профили
            profiles = await self.hass.async_add_executor_job(
                self._media.GetProfiles
            )
            
            if not profiles:
                _LOGGER.error("❌ No media profiles found")
                return False
                
            self._profile = profiles[0]
            _LOGGER.debug(f"Using media profile: {self._profile.Name}")

            # Пытаемся получить PTZ сервис
            try:
                self._ptz = await self.hass.async_add_executor_job(
                    self._cam.create_ptz_service
                )
                # Проверяем поддержку PTZ
                if self._ptz:
                    ptz_status = await self.async_get_ptz_status()
                    _LOGGER.info(f"✅ PTZ supported, current position: {ptz_status}")
            except Exception as err:
                _LOGGER.info(f"ℹ️ PTZ not supported for this device: {err}")
                self._ptz = None

            # Пытаемся получить Event сервис
            try:
                self._events = await self.hass.async_add_executor_job(
                    self._cam.create_events_service
                )
                await self.async_subscribe_events()
            except Exception as err:
                _LOGGER.info(f"ℹ️ Events not supported: {err}")
                self._events = None

            self._available = True
            _LOGGER.info(f"✅ ONVIF connection successful for {self.camera_name}")
            return True

        except Exception as err:
            _LOGGER.error(f"❌ ONVIF connection failed: {err}")
            self._available = False
            return False

    async def async_disconnect(self):
        """Disconnect ONVIF client."""
        self._available = False
        _LOGGER.info(f"Disconnected ONVIF client for {self.camera_name}")

    # ========== PTZ Control ==========

    async def async_ptz_move(self, direction: str, speed: Optional[float] = None) -> bool:
        """Move PTZ camera."""
        if not self._ptz or not self._available:
            _LOGGER.warning("PTZ not available")
            return False

        speed = speed or self._ptz_speed

        try:
            # Создаем запрос на движение
            request = self._ptz.create_type('ContinuousMove')
            request.ProfileToken = self._profile.token
            request.Velocity = {
                'PanTilt': {
                    'x': 0.0,
                    'y': 0.0
                },
                'Zoom': {
                    'x': 0.0
                }
            }

            # Устанавливаем направление [citation:2]
            if direction in ['left', 'left_up', 'left_down']:
                request.Velocity['PanTilt']['x'] = -speed
            elif direction in ['right', 'right_up', 'right_down']:
                request.Velocity['PanTilt']['x'] = speed

            if direction in ['up', 'left_up', 'right_up']:
                request.Velocity['PanTilt']['y'] = speed
            elif direction in ['down', 'left_down', 'right_down']:
                request.Velocity['PanTilt']['y'] = -speed

            if direction == 'zoom_in':
                request.Velocity['Zoom']['x'] = speed
            elif direction == 'zoom_out':
                request.Velocity['Zoom']['x'] = -speed

            await self.hass.async_add_executor_job(
                self._ptz.ContinuousMove,
                request
            )

            _LOGGER.debug(f"PTZ move: {direction} at speed {speed}")
            return True

        except Exception as err:
            _LOGGER.error(f"PTZ move failed: {err}")
            return False

    async def async_ptz_stop(self) -> bool:
        """Stop PTZ movement."""
        if not self._ptz or not self._available:
            return False

        try:
            request = self._ptz.create_type('Stop')
            request.ProfileToken = self._profile.token
            request.PanTilt = True
            request.Zoom = True

            await self.hass.async_add_executor_job(
                self._ptz.Stop,
                request
            )

            _LOGGER.debug("PTZ stopped")
            return True

        except Exception as err:
            _LOGGER.error(f"PTZ stop failed: {err}")
            return False

    async def async_ptz_goto_preset(self, preset_token: str) -> bool:
        """Go to preset position."""
        if not self._ptz or not self._available:
            return False

        try:
            request = self._ptz.create_type('GotoPreset')
            request.ProfileToken = self._profile.token
            request.PresetToken = preset_token

            await self.hass.async_add_executor_job(
                self._ptz.GotoPreset,
                request
            )

            _LOGGER.info(f"PTZ goto preset: {preset_token}")
            return True

        except Exception as err:
            _LOGGER.error(f"PTZ goto preset failed: {err}")
            return False

    async def async_ptz_set_preset(self, preset_name: str) -> Optional[str]:
        """Set current position as preset."""
        if not self._ptz or not self._available:
            return None

        try:
            request = self._ptz.create_type('SetPreset')
            request.ProfileToken = self._profile.token
            request.PresetName = preset_name

            result = await self.hass.async_add_executor_job(
                self._ptz.SetPreset,
                request
            )

            # Обновляем кэш пресетов
            await self.async_update_presets()

            preset_token = result.PresetToken if hasattr(result, 'PresetToken') else None
            _LOGGER.info(f"Preset set: {preset_name} ({preset_token})")
            return preset_token

        except Exception as err:
            _LOGGER.error(f"Set preset failed: {err}")
            return None

    async def async_ptz_remove_preset(self, preset_token: str) -> bool:
        """Remove preset."""
        if not self._ptz or not self._available:
            return False

        try:
            request = self._ptz.create_type('RemovePreset')
            request.ProfileToken = self._profile.token
            request.PresetToken = preset_token

            await self.hass.async_add_executor_job(
                self._ptz.RemovePreset,
                request
            )

            # Обновляем кэш
            await self.async_update_presets()

            _LOGGER.info(f"Preset removed: {preset_token}")
            return True

        except Exception as err:
            _LOGGER.error(f"Remove preset failed: {err}")
            return False

    async def async_update_presets(self) -> Dict[str, str]:
        """Get all presets."""
        if not self._ptz or not self._available:
            return {}

        try:
            request = self._ptz.create_type('GetPresets')
            request.ProfileToken = self._profile.token

            presets = await self.hass.async_add_executor_job(
                self._ptz.GetPresets,
                request
            )

            # Преобразуем в словарь {name: token}
            self._presets = {
                p.Name: p.token for p in presets if hasattr(p, 'Name')
            }

            _LOGGER.debug(f"Found {len(self._presets)} presets")
            return self._presets

        except Exception as err:
            _LOGGER.error(f"Get presets failed: {err}")
            return {}

    async def async_get_ptz_status(self) -> Optional[Dict[str, float]]:
        """Get current PTZ position."""
        if not self._ptz or not self._available:
            return None

        try:
            request = self._ptz.create_type('GetStatus')
            request.ProfileToken = self._profile.token

            status = await self.hass.async_add_executor_job(
                self._ptz.GetStatus,
                request
            )

            if hasattr(status, 'Position') and status.Position:
                pos = status.Position
                return {
                    'pan': pos.PanTilt.x if hasattr(pos, 'PanTilt') else 0,
                    'tilt': pos.PanTilt.y if hasattr(pos, 'PanTilt') else 0,
                    'zoom': pos.Zoom.x if hasattr(pos, 'Zoom') else 0,
                }
            return None

        except Exception as err:
            _LOGGER.error(f"Get PTZ status failed: {err}")
            return None

    # ========== Event Handling ==========

    async def async_subscribe_events(self):
        """Subscribe to ONVIF events."""
        if not self._events or not self._available:
            return

        try:
            # Создаем pull point subscription
            subscription = await self.hass.async_add_executor_job(
                self._events.CreatePullPointSubscription
            )
            
            # Запускаем polling событий
            self.hass.async_create_task(self._async_pull_events(subscription))

        except Exception as err:
            _LOGGER.error(f"Event subscription failed: {err}")

    async def _async_pull_events(self, subscription):
        """Pull events from subscription."""
        while self._available:
            try:
                messages = await self.hass.async_add_executor_job(
                    subscription.PullMessages,
                    10  # timeout
                )

                for msg in messages:
                    await self._async_process_event(msg)

                await asyncio.sleep(1)

            except Exception as err:
                _LOGGER.debug(f"Event pull error: {err}")
                await asyncio.sleep(5)

    async def _async_process_event(self, message):
        """Process ONVIF event message."""
        try:
            # Парсим сообщение (упрощенно)
            event_data = {
                'source': message.get('Source', {}),
                'data': message.get('Data', {}),
                'timestamp': datetime.now().isoformat(),
            }

            # Вызываем колбэки
            for callback in self._event_callbacks:
                await callback(event_data)

        except Exception as err:
            _LOGGER.error(f"Event processing failed: {err}")

    def register_event_callback(self, callback: Callable):
        """Register event callback."""
        self._event_callbacks.append(callback)

    def unregister_event_callback(self, callback: Callable):
        """Unregister event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    # ========== Properties ==========

    @property
    def is_available(self) -> bool:
        """Return True if ONVIF is available."""
        return self._available

    @property
    def has_ptz(self) -> bool:
        """Return True if PTZ is supported."""
        return self._ptz is not None

    @property
    def presets(self) -> Dict[str, str]:
        """Return available presets."""
        return self._presets

    @property
    def ptz_speed(self) -> float:
        """Return PTZ speed."""
        return self._ptz_speed

    @ptz_speed.setter
    def ptz_speed(self, speed: float):
        """Set PTZ speed."""
        self._ptz_speed = max(0.0, min(1.0, speed))

    @property
    def stream_uri(self) -> Optional[str]:
        """Get RTSP stream URI."""
        if not self._media or not self._profile:
            return None

        try:
            return self._profile.StreamUri
        except:
            return None
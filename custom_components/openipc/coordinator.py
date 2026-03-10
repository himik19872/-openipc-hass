"""Coordinator for OpenIPC integration."""
import asyncio
import logging
import time
import re
from datetime import timedelta

import aiohttp
import async_timeout
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    API_STATUS,
    DEFAULT_SCAN_INTERVAL,
    CONF_RTSP_PORT,
    MAJESTIC_CONFIG,
    METRICS_ENDPOINT,
    RECORD_START,
    RECORD_STOP,
    RECORD_STATUS,
    RECORD_MANUAL,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_BEWARD,
    DEVICE_TYPE_VIVOTEK,
    LNPR_STATE,
    LNPR_LIST,
)
from .recorder import OpenIPCRecorder
from .addon import OpenIPCAddonManager

_LOGGER = logging.getLogger(__name__)

class OpenIPCDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OpenIPC data."""

    def __init__(self, hass, entry):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.data.get('name', entry.data[CONF_HOST])}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.rtsp_port = entry.data.get(CONF_RTSP_PORT, 554)
        
        self.session = async_get_clientsession(hass)
        self.auth = aiohttp.BasicAuth(self.username, self.password)
        
        self._cache = {}
        self._cache_time = {}
        
        camera_name = entry.data.get('name', 'OpenIPC Camera')
        self.recorder = OpenIPCRecorder(
            hass,
            self.host,
            self.port,
            self.username,
            self.password,
            camera_name
        )
        
        self.beward = None
        self.vivotek = None
        self.openipc_audio = None
        self.qr_scanner = None
        self.addon = None
        self.use_addon = False
        
        # Определяем тип камеры
        self.is_beward = (entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_BEWARD)
        self.is_vivotek = (entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_VIVOTEK)
        
        # Инициализируем Beward device если нужно
        if self.is_beward:
            try:
                from .beward_device import OpenIPCBewardDevice
                self.beward = OpenIPCBewardDevice(
                    hass,
                    self.host,
                    self.username,
                    self.password,
                    camera_name
                )
                # Запускаем подключение в фоне
                hass.async_create_task(self._async_connect_beward())
                _LOGGER.info(f"✅ Beward device created for {camera_name}")
            except Exception as err:
                _LOGGER.error(f"❌ Failed to create Beward device: {err}")
        
        # Инициализируем Vivotek device если нужно
        if self.is_vivotek:
            try:
                from .vivotek_device import OpenIPCVivotekDevice
                self.vivotek = OpenIPCVivotekDevice(
                    hass,
                    self.host,
                    self.username,
                    self.password,
                    camera_name
                )
                hass.async_create_task(self._async_connect_vivotek())
                _LOGGER.info(f"✅ Vivotek device created for {camera_name}")
            except Exception as err:
                _LOGGER.error(f"❌ Failed to create Vivotek device: {err}")
        
        # Явно создаем и проверяем аддон
        self.addon = OpenIPCAddonManager(hass)
        
        # Запускаем задачу для обнаружения аддона
        hass.async_create_task(self._async_discover_addon())
        
        self.recording_duration = 60
        self._recording_task = None
        self._recording_end_time = None
        self._ha_recording_task = None

    async def _async_connect_beward(self):
        """Connect to Beward device."""
        if self.beward:
            try:
                await self.beward.async_connect()
                _LOGGER.info(f"✅ Beward device connected at {self.host}")
            except Exception as err:
                _LOGGER.error(f"❌ Failed to connect Beward device: {err}")

    async def _async_connect_vivotek(self):
        """Connect to Vivotek device."""
        if self.vivotek:
            try:
                await self.vivotek.async_test_connection()
                _LOGGER.info(f"✅ Vivotek device connected at {self.host}")
            except Exception as err:
                _LOGGER.error(f"❌ Failed to connect Vivotek device: {err}")

    async def _async_discover_addon(self):
        """Discover addon asynchronously."""
        try:
            if self.addon:
                _LOGGER.info("🔍 Attempting to discover OpenIPC Bridge addon...")
                
                # Пробуем несколько раз с задержкой
                for attempt in range(3):
                    found = await self.addon.async_discover_addon()
                    if found:
                        self.use_addon = True
                        _LOGGER.info(f"✅ OpenIPC Bridge addon discovered and connected! (attempt {attempt + 1})")
                        
                        # Если есть QR сканер, обновляем его
                        if hasattr(self, 'qr_scanner') and self.qr_scanner:
                            self.qr_scanner.use_addon = True
                        return True
                    else:
                        if attempt < 2:  # Не ждем после последней попытки
                            _LOGGER.warning(f"⚠️ Addon discovery attempt {attempt + 1} failed, retrying in 2 seconds...")
                            await asyncio.sleep(2)
                
                _LOGGER.warning("❌ OpenIPC Bridge addon not found after 3 attempts")
                return False
        except Exception as err:
            _LOGGER.error("Error discovering addon: %s", err)
            return False

    async def _async_update_data(self):
        """Fetch data from camera."""
        try:
            async with async_timeout.timeout(10):
                _LOGGER.debug("Attempting to fetch data from camera %s", self.host)
                
                config_data = await self._get_json_config()
                metrics_data = await self._get_metrics()
                status_data = await self._get_camera_status()
                recording_status = await self.async_get_recording_status()
                
                parsed_data = self._parse_camera_data(config_data, metrics_data, status_data)
                
                if recording_status:
                    parsed_data["recording_status"] = recording_status.get("recording", False)
                    parsed_data["recording_remaining"] = recording_status.get("remaining", 0)
                    parsed_data["recording_end_time"] = recording_status.get("end_time", 0)
                
                data = {
                    "config": config_data,
                    "metrics": metrics_data,
                    "status": status_data,
                    "recording": recording_status,
                    "parsed": parsed_data,
                    "available": True,
                    "last_update": self.hass.loop.time(),
                }
                
                if self.beward:
                    lnpr_data = await self._async_update_lnpr()
                    data["lnpr"] = lnpr_data
                
                return data
                
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout fetching camera data from %s", self.host)
            if self.data:
                return {**self.data, "available": False}
            raise UpdateFailed(f"Timeout connecting to camera {self.host}")
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                _LOGGER.error("Authentication failed for camera %s", self.host)
                if self.data:
                    return {**self.data, "available": False}
                raise UpdateFailed(f"Authentication failed for camera {self.host}")
            else:
                _LOGGER.error("HTTP error %d from %s", err.status, self.host)
                if self.data:
                    return {**self.data, "available": False}
                raise UpdateFailed(f"HTTP error {err.status} from camera {self.host}")
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("Connection error for camera %s: %s", self.host, err)
            if self.data:
                return {**self.data, "available": False}
            raise UpdateFailed(f"Cannot connect to camera {self.host}")
        except Exception as err:
            _LOGGER.error("Error updating data from %s: %s", self.host, err)
            if self.data:
                return {**self.data, "available": False}
            raise UpdateFailed(f"Error communicating with camera {self.host}: {err}")

    def _parse_camera_data(self, config, metrics, status):
        """Parse data from JSON config, Prometheus metrics and HTML status."""
        from .parsers import parse_camera_data
        return parse_camera_data(config, metrics, status)

    async def _async_update_lnpr(self):
        """Fetch LNPR data from camera."""
        from .lnpr import async_update_lnpr
        return await async_update_lnpr(self)

    async def _check_plate_authorized(self, plate: str) -> bool:
        """Check if plate is in whitelist."""
        from .lnpr import check_plate_authorized
        return await check_plate_authorized(self, plate)

    async def _get_json_config(self):
        """Get JSON configuration from camera."""
        from .api import get_json_config
        return await get_json_config(self)

    async def _get_metrics(self):
        """Get Prometheus metrics from camera."""
        from .api import get_metrics
        return await get_metrics(self)

    async def _get_camera_status(self):
        """Get camera status from HTML endpoint."""
        from .api import get_camera_status
        return await get_camera_status(self)

    async def async_send_command(self, command, params=None):
        """Send command to camera."""
        from .api import send_command
        return await send_command(self, command, params)

    async def async_set_night_mode(self, mode: str):
        """Set night mode (on/off/auto)."""
        from .commands import set_night_mode
        return await set_night_mode(self, mode)

    async def async_start_recording(self):
        """Start recording on camera SD card."""
        from .recording import start_recording
        return await start_recording(self)

    async def async_stop_recording(self):
        """Stop recording on camera SD card."""
        from .recording import stop_recording
        return await stop_recording(self)

    async def async_record_to_ha_media(self, duration: int, method: str = "snapshots") -> dict:
        """Record video directly to Home Assistant media folder."""
        from .recording import record_to_ha_media
        return await record_to_ha_media(self, duration, method)

    async def async_start_timed_recording(self, duration: int, save_to_ha: bool = True, method: str = "snapshots"):
        """Start recording for specified duration."""
        from .recording import start_timed_recording
        return await start_timed_recording(self, duration, save_to_ha, method)

    async def async_get_recording_status(self):
        """Get recording status."""
        from .recording import get_recording_status
        return await get_recording_status(self)

    async def async_record_and_send_telegram(self, duration: int, method: str = "snapshots",
                                            caption: str = None, chat_id: str = None) -> dict:
        """Record video and send to Telegram."""
        from .recording import record_and_send_telegram
        return await record_and_send_telegram(self, duration, method, caption, chat_id)

    async def async_diagnose_rtsp(self):
        """Diagnose RTSP stream."""
        from .diagnostics import diagnose_rtsp
        return await diagnose_rtsp(self)

    async def async_diagnose_telegram(self):
        """Diagnose Telegram configuration."""
        from .diagnostics import diagnose_telegram
        return await diagnose_telegram(self)

    async def async_test_telegram(self, chat_id: str = None):
        """Test Telegram file send."""
        from .diagnostics import test_telegram
        return await test_telegram(self, chat_id)
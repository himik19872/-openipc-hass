"""Beward device support for OpenIPC integration."""
import logging
import aiohttp
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

# Типы моделей Beward
MODEL_TYPE_MULTI = "multi"  # Многоабонентские DKS***
MODEL_TYPE_SINGLE = "single"  # Одноабонентские DS** (DS07P-LP)

class OpenIPCBewardDevice:
    """Beward device handler for DS07P-LP model."""

    def __init__(self, hass: HomeAssistant, host: str, username: str, password: str, camera_name: str):
        """Initialize Beward device."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.camera_name = camera_name
        self.session = async_get_clientsession(hass)
        self._auth = aiohttp.BasicAuth(username, password)
        
        self._available = False
        self._model_type = MODEL_TYPE_SINGLE  # По умолчанию одноабонентская для DS07P-LP
        
        # Состояния
        self._state = {
            "online": False,
            "motion": False,
            "door": False,
            "sound": False,
            "temperature": None,
            "last_motion": None,
            "last_door": None,
            "last_sound": None,
        }
        
        _LOGGER.info(f"✅ Beward DS07P-LP device handler created for {camera_name} at {host}")

    @property
    def is_available(self) -> bool:
        """Return True if device is available."""
        return self._available

    @property
    def state(self) -> Dict[str, Any]:
        """Return current device state."""
        return self._state.copy()

    @property
    def model_type(self) -> str:
        """Return detected model type."""
        return self._model_type

    @property
    def motion_detected(self) -> bool:
        """Return True if motion detected."""
        return self._state.get("motion", False)

    @property
    def sensor_triggered(self) -> bool:
        """Return True if door sensor triggered."""
        return self._state.get("door", False)

    async def detect_model_type(self) -> str:
        """Detect Beward model type by trying different endpoints."""
        _LOGGER.info("🔍 Detecting Beward model type for %s", self.host)
        
        # Проверяем доступность камеры через основной эндпоинт
        try:
            async with self.session.get(
                f"http://{self.host}/cgi-bin/status.cgi",
                auth=self._auth,
                timeout=5
            ) as response:
                if response.status == 200:
                    _LOGGER.info("✅ Camera is accessible via status.cgi")
                else:
                    _LOGGER.warning("⚠️ Camera returned status %d", response.status)
        except Exception as err:
            _LOGGER.error("❌ Camera not accessible: %s", err)
            return None
        
        # Пробуем эндпоинт для многоабонентской модели (intercom_cgi)
        try:
            url = f"http://{self.host}/cgi-bin/intercom_cgi?action=status"
            _LOGGER.debug("Trying multi-tenant endpoint: %s", url)
            async with self.session.get(url, auth=self._auth, timeout=3) as response:
                if response.status == 200:
                    text = await response.text()
                    if any(x in text.lower() for x in ['intercom', 'door', 'relay']):
                        _LOGGER.info("✅ Detected multi-tenant model (DKS***)")
                        self._model_type = MODEL_TYPE_MULTI
                        return MODEL_TYPE_MULTI
                    else:
                        _LOGGER.debug("Response from multi-tenant endpoint: %s", text[:100])
        except Exception as err:
            _LOGGER.debug("Multi-tenant endpoint failed: %s", err)
        
        # Пробуем эндпоинт для одноабонентской модели (alarmout_cgi) - для DS07P-LP
        try:
            url = f"http://{self.host}/cgi-bin/alarmout_cgi?Output=0"
            _LOGGER.debug("Trying single-tenant endpoint: %s", url)
            async with self.session.get(url, auth=self._auth, timeout=3) as response:
                if response.status == 200:
                    _LOGGER.info("✅ Detected single-tenant model (DS07P-LP)")
                    self._model_type = MODEL_TYPE_SINGLE
                    return MODEL_TYPE_SINGLE
        except Exception as err:
            _LOGGER.debug("Single-tenant endpoint failed: %s", err)
        
        # Пробуем определить по странице логина
        try:
            url = f"http://{self.host}/login.asp"
            async with self.session.get(url, auth=self._auth, timeout=3) as response:
                if response.status == 200:
                    text = await response.text()
                    if 'Beward' in text:
                        _LOGGER.info("✅ Detected Beward via login page")
                        self._model_type = MODEL_TYPE_SINGLE  # Предполагаем одноабонентскую
                        return MODEL_TYPE_SINGLE
        except:
            pass
        
        _LOGGER.warning("⚠️ Could not detect model type, assuming single-tenant (DS07P-LP)")
        return self._model_type

    async def async_connect(self) -> bool:
        """Connect to Beward device."""
        try:
            # Определяем тип модели
            await self.detect_model_type()
            
            # Проверяем доступность через status.cgi
            async with self.session.get(
                f"http://{self.host}/cgi-bin/status.cgi",
                auth=self._auth,
                timeout=5
            ) as response:
                if response.status == 200:
                    self._available = True
                    self._state["online"] = True
                    _LOGGER.info(f"✅ Connected to Beward DS07P-LP at {self.host}")
                    return True
                else:
                    _LOGGER.error(f"❌ Failed to connect: HTTP {response.status}")
                    return False
                    
        except Exception as err:
            _LOGGER.error(f"❌ Failed to connect to Beward device: {err}")
            self._available = False
            return False

    async def async_get_snapshot(self) -> Optional[bytes]:
        """Get snapshot from camera."""
        # Пробуем разные эндпоинты для снимков
        snapshot_urls = [
            f"http://{self.host}/cgi-bin/image.cgi",
            f"http://{self.host}/cgi-bin/jpg/image.cgi",
            f"http://{self.host}/cgi-bin/snapshot.cgi",
            f"http://{self.host}/snapshot.jpg",
            f"http://{self.host}/image.jpg",
            f"http://{self.host}/cgi-bin/video.cgi",  # Может вернуть первый кадр
        ]
        
        for url in snapshot_urls:
            try:
                _LOGGER.debug("Trying Beward snapshot URL: %s", url)
                async with self.session.get(
                    url,
                    auth=self._auth,
                    timeout=5
                ) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '')
                        data = await response.read()
                        
                        # Проверяем, что это изображение
                        if len(data) > 1000:
                            # Проверяем JPEG signature
                            if data[0:2] == b'\xff\xd8':
                                _LOGGER.info(f"✅ Beward JPEG snapshot successful from {url} ({len(data)} bytes)")
                                return data
                            # Проверяем PNG signature
                            elif data[0:8] == b'\x89PNG\r\n\x1a\n':
                                _LOGGER.info(f"✅ Beward PNG snapshot successful from {url} ({len(data)} bytes)")
                                return data
                            else:
                                _LOGGER.info(f"✅ Beward snapshot data from {url} ({len(data)} bytes)")
                                return data
                        else:
                            _LOGGER.warning(f"Data too small from {url}: {len(data)} bytes")
            except Exception as err:
                _LOGGER.debug("Snapshot URL %s failed: %s", url, err)
                continue
        
        _LOGGER.error("❌ All Beward snapshot URLs failed")
        return None

    async def async_open_door(self, main: bool = True) -> bool:
        """Open door via HTTP API for DS07P-LP model."""
        _LOGGER.info(f"🚪 Opening door on Beward DS07P-LP (main: {main})")
        
        # Для одноабонентских моделей DS** используем alarmout_cgi
        relay = 0 if main else 1
        
        # URL для включения реле
        url_on = f"http://{self.username}:{self.password}@{self.host}/cgi-bin/alarmout_cgi?Output={relay}&Status=1"
        url_off = f"http://{self.username}:{self.password}@{self.host}/cgi-bin/alarmout_cgi?Output={relay}&Status=0"
        
        try:
            _LOGGER.debug("Activating relay %d: %s", relay, url_on)
            async with self.session.get(url_on, timeout=3) as response:
                if response.status == 200:
                    _LOGGER.info(f"✅ Relay {relay} activated")
                    
                    # Ждем 1 секунду
                    await asyncio.sleep(1)
                    
                    # Выключаем реле
                    _LOGGER.debug("Deactivating relay: %s", url_off)
                    async with self.session.get(url_off, timeout=3) as off_response:
                        if off_response.status == 200:
                            _LOGGER.info(f"✅ Door opened successfully")
                            return True
                        else:
                            _LOGGER.warning(f"Relay deactivation returned HTTP {off_response.status}")
                            return True  # Дверь все равно открылась
                else:
                    _LOGGER.error(f"❌ Door open failed: HTTP {response.status}")
                    return False
                    
        except Exception as err:
            _LOGGER.error(f"Door open error: {err}")
            return False

    @property
    def snapshot_url(self) -> str:
        """Get snapshot URL."""
        return f"http://{self.host}/cgi-bin/image.cgi"

    @property
    def mjpeg_url(self) -> str:
        """Get MJPEG stream URL."""
        return f"http://{self.host}/cgi-bin/video.cgi"

    @property
    def rtsp_url_main(self) -> str:
        """Get main RTSP stream URL for DS07P-LP with port 554."""
        return f"rtsp://{self.username}:{self.password}@{self.host}:554/av0_0"

    @property
    def rtsp_url_sub(self) -> str:
        """Get sub RTSP stream URL for DS07P-LP with port 554."""
        return f"rtsp://{self.username}:{self.password}@{self.host}:554/av0_1"
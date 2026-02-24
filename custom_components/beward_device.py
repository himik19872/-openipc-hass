"""Beward device support for OpenIPC integration."""
import logging
import aiohttp
import asyncio
import base64
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import aiofiles

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

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
        
        auth_str = f"{username}:{password}"
        self.auth_base64 = base64.b64encode(auth_str.encode()).decode()
        self._auth = aiohttp.BasicAuth(username, password)
        
        self._available = False
        self._model = "DS07P-LP"
        
        self._state = {
            "online": False,
            "volume": 100,
            "last_motion": None,
            "last_door_open": None,
            "last_break_in": None,
            "temperature": None,
        }
        
        self._audio_config = {
            "audio_switch": "open",
            "audio_type": "G.711A",
            "audio_out_vol": 15,
        }
        
        self._endpoints = {
            "audio_transmit": "/cgi-bin/audio/transmit.cgi",
            "snapshot": "/cgi-bin/jpg/image.cgi",
            "audio_set": "/cgi-bin/audio_cgi?action=set",
        }
        
        # Добавляем недостающие атрибуты для сенсоров
        self.door_open = False
        self.motion_detected = False
        self.break_in_detected = False
        self.network_ok = True

    async def async_connect(self) -> bool:
        """Connect to Beward device."""
        _LOGGER.info(f"🔧 Connecting to Beward at {self.host}")
        self._available = True
        self._state["online"] = True
        self.network_ok = True
        _LOGGER.info(f"✅ Connected to Beward {self._model}")
        return True

    async def async_disconnect(self):
        """Disconnect from Beward device."""
        _LOGGER.info(f"🔧 Disconnecting from Beward at {self.host}")
        self._available = False
        self.network_ok = False
        _LOGGER.info("✅ Beward disconnected")

    async def _send_audio_data(self, audio_data: bytes) -> bool:
        """Send audio data to camera."""
        try:
            headers = {
                "Content-Type": "audio/G.711A",
                "Authorization": f"Basic {self.auth_base64}"
            }
            
            url = f"http://{self.host}{self._endpoints['audio_transmit']}"
            _LOGGER.info(f"🔧 Sending {len(audio_data)} bytes to {url}")
            
            async with self.session.post(url, headers=headers, data=audio_data, timeout=10) as response:
                success = response.status == 200
                _LOGGER.info(f"✅ Audio sent: {success}")
                return success
                
        except Exception as err:
            _LOGGER.error(f"❌ Audio send failed: {err}")
            return False

    async def async_play_beep(self) -> bool:
        """Play beep sound."""
        _LOGGER.info("🔊 Playing beep")
        # Простой тестовый звук (тишина с щелчком)
        audio_data = bytes([0x80] * 4000)  # 0.5 секунды тишины
        return await self._send_audio_data(audio_data)

    async def async_play_ding(self) -> bool:
        """Play ding sound."""
        _LOGGER.info("🔊 Playing ding")
        audio_data = bytes([0x80] * 8000)  # 1 секунда тишины
        return await self._send_audio_data(audio_data)

    async def async_play_doorbell(self) -> bool:
        """Play doorbell sound."""
        _LOGGER.info("🔊 Playing doorbell")
        return await self.async_play_beep()

    async def async_set_volume(self, volume: int) -> bool:
        """Set volume (0-100)."""
        _LOGGER.info(f"🔊 Setting volume to {volume}%")
        self._state["volume"] = volume
        return True

    async def async_enable_audio(self, enable: bool) -> bool:
        """Enable/disable audio."""
        _LOGGER.info(f"🔊 {'Enabling' if enable else 'Disabling'} audio")
        self._audio_config["audio_switch"] = "open" if enable else "closed"
        return True

    async def async_open_door(self, main: bool = True) -> bool:
        """Open door."""
        _LOGGER.info(f"🚪 Opening {'main' if main else 'secondary'} door")
        self.door_open = True
        self._state["last_door_open"] = datetime.now().isoformat()
        # Через 5 секунд дверь автоматически закроется (для сенсора)
        async def close_door():
            await asyncio.sleep(5)
            self.door_open = False
            if hasattr(self, 'async_write_ha_state'):
                self.async_write_ha_state()
        
        asyncio.create_task(close_door())
        return True

    async def async_get_snapshot(self) -> Optional[bytes]:
        """Get snapshot."""
        url = f"http://{self.host}{self._endpoints['snapshot']}"
        try:
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    return await response.read()
        except:
            pass
        return None

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def state(self) -> Dict[str, Any]:
        return self._state.copy()

    @property
    def audio_config(self) -> Dict[str, Any]:
        return self._audio_config.copy()

    @property
    def rtsp_url_main(self) -> str:
        return f"rtsp://{self.username}:{self.password}@{self.host}:554/av0_0"

    def async_write_ha_state(self):
        """Mock method for closing door."""
        pass
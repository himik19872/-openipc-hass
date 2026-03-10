"""OpenIPC Add-on manager."""
import logging
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

class OpenIPCAddonManager:
    """Manager for OpenIPC Bridge add-on."""

    def __init__(self, hass: HomeAssistant):
        """Initialize add-on manager."""
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self._addon_info = None
        self._api_url = None
        self._available = False

    async def async_discover_addon(self) -> bool:
        """Discover if OpenIPC Bridge add-on is running."""
        # Пробуем разные возможные адреса
        possible_urls = [
            "http://openipc-bridge:5000",  # Docker service name
            "http://openipc_bridge:5000",
            "http://172.30.32.2:5000",     # Supervisor container IP
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://supervisor:5000",      # Supervisor hostname
            "http://homeassistant:5000",   # Home Assistant hostname
        ]
        
        _LOGGER.info("🔍 Scanning for OpenIPC Bridge addon...")
        
        for url in possible_urls:
            try:
                _LOGGER.debug(f"Trying add-on at {url}")
                async with self.session.get(f"{url}/health", timeout=2) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._api_url = url
                        self._addon_info = data
                        self._available = True
                        _LOGGER.info(f"✅ OpenIPC Bridge add-on found at {url}")
                        _LOGGER.info(f"   Version: {data.get('version', 'unknown')}")
                        _LOGGER.info(f"   Cameras: {data.get('capabilities', {}).get('cameras', 0)}")
                        return True
            except asyncio.TimeoutError:
                _LOGGER.debug(f"Timeout connecting to {url}")
                continue
            except aiohttp.ClientConnectorError as e:
                _LOGGER.debug(f"Connection error to {url}: {e}")
                continue
            except Exception as e:
                _LOGGER.debug(f"Failed to connect to {url}: {e}")
                continue

        _LOGGER.warning("❌ OpenIPC Bridge add-on not found")
        return False

    @property
    def available(self) -> bool:
        """Return True if add-on is available."""
        return self._available

    @property
    def api_url(self) -> Optional[str]:
        """Return API URL."""
        return self._api_url

    @property
    def info(self) -> Optional[Dict]:
        """Return add-on info."""
        return self._addon_info

    async def async_tts(self, camera_id: str, message: str, language: str = "ru") -> bool:
        """Send TTS request to add-on."""
        if not self._available:
            return False

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/tts"
            payload = {
                "message": message,
                "language": language
            }
            
            async with self.session.post(url, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("success", False)
                else:
                    _LOGGER.error(f"TTS failed: HTTP {resp.status}")
                    return False
        except Exception as err:
            _LOGGER.error(f"TTS error: {err}")
            return False

    async def async_qr_scan(self, camera_id: str, timeout: int = 30) -> Optional[List[Dict]]:
        """Trigger QR scan."""
        if not self._available:
            return None

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/qr/scan"
            payload = {"timeout": timeout}
            
            async with self.session.post(url, json=payload, timeout=timeout+5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("results", [])
                else:
                    _LOGGER.error(f"QR scan failed: HTTP {resp.status}")
                    return None
        except Exception as err:
            _LOGGER.error(f"QR scan error: {err}")
            return None

    async def async_start_scan(self, camera_id: str, expected_code: str, timeout: int) -> Optional[Dict]:
        """Start continuous QR scan."""
        if not self._available:
            return None

        try:
            url = f"{self._api_url}/api/start_scan"
            payload = {
                "camera_id": camera_id,
                "expected_code": expected_code,
                "timeout": timeout
            }
            
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error(f"Start scan failed: HTTP {resp.status}")
                    return None
        except Exception as err:
            _LOGGER.error(f"Start scan error: {err}")
            return None

    async def async_snapshot(self, camera_id: str) -> Optional[bytes]:
        """Get snapshot from camera."""
        if not self._available:
            return None

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/snapshot"
            
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    _LOGGER.error(f"Snapshot failed: HTTP {resp.status}")
                    return None
        except Exception as err:
            _LOGGER.error(f"Snapshot error: {err}")
            return None

    async def async_lnpr_add(self, camera_id: str, plate: str, **kwargs) -> bool:
        """Add plate to LNPR whitelist."""
        if not self._available:
            return False

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/lnpr/add"
            payload = {"plate": plate, **kwargs}
            
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("success", False)
                else:
                    _LOGGER.error(f"LNPR add failed: HTTP {resp.status}")
                    return False
        except Exception as err:
            _LOGGER.error(f"LNPR add error: {err}")
            return False

    async def async_lnpr_list(self, camera_id: str) -> Optional[List[str]]:
        """Get LNPR whitelist."""
        if not self._available:
            return None

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/lnpr/list"
            
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("plates", [])
                else:
                    _LOGGER.error(f"LNPR list failed: HTTP {resp.status}")
                    return None
        except Exception as err:
            _LOGGER.error(f"LNPR list error: {err}")
            return None

    async def async_lnpr_delete(self, camera_id: str, plate: str) -> bool:
        """Delete plate from LNPR whitelist."""
        if not self._available:
            return False

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/lnpr/delete"
            payload = {"plate": plate}
            
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("success", False)
                else:
                    _LOGGER.error(f"LNPR delete failed: HTTP {resp.status}")
                    return False
        except Exception as err:
            _LOGGER.error(f"LNPR delete error: {err}")
            return False

    async def async_ptz_move(self, camera_id: str, direction: str, speed: int = 50) -> bool:
        """Move PTZ camera."""
        if not self._available:
            return False

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/ptz/move"
            payload = {
                "direction": direction,
                "speed": speed
            }
            
            async with self.session.post(url, json=payload, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("success", False)
                else:
                    _LOGGER.error(f"PTZ move failed: HTTP {resp.status}")
                    return False
        except Exception as err:
            _LOGGER.error(f"PTZ move error: {err}")
            return False

    async def async_ptz_preset(self, camera_id: str, action: str, preset_id: int, name: str = None) -> bool:
        """Control PTZ presets."""
        if not self._available:
            return False

        try:
            url = f"{self._api_url}/api/camera/{camera_id}/ptz/preset"
            payload = {
                "action": action,
                "preset_id": preset_id
            }
            if name:
                payload["name"] = name
            
            async with self.session.post(url, json=payload, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("success", False)
                else:
                    _LOGGER.error(f"PTZ preset failed: HTTP {resp.status}")
                    return False
        except Exception as err:
            _LOGGER.error(f"PTZ preset error: {err}")
            return False
"""Vivotek device support for OpenIPC integration."""
import logging
import aiohttp
import asyncio
import os
import tempfile
from typing import Optional, Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import aiofiles

_LOGGER = logging.getLogger(__name__)

class OpenIPCVivotekDevice:
    """Vivotek device handler for SD9364-EHL based on actual camera configuration."""

    def __init__(self, hass: HomeAssistant, host: str, username: str, password: str, camera_name: str):
        """Initialize Vivotek device."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.camera_name = camera_name
        self.session = async_get_clientsession(hass)
        
        self._available = False
        self._auth = aiohttp.BasicAuth(username, password)
        
        # Настройки из конфигурации камеры
        self.http_port = 80
        self.rtsp_port = 554
        
        # Имена потоков из конфигурации
        self.rtsp_streams = {
            1: "live.sdp",
            2: "live2.sdp",
            3: "live3.sdp",
            4: "live4.sdp"
        }
        
        self.http_streams = {
            1: "video.mjpg",
            2: "video2.mjpg",
            3: "video3.mjpg",
            4: "video4.mjpg"
        }
        
        _LOGGER.info(f"✅ Vivotek SD9364-EHL device handler created for {camera_name} at {host}")
        _LOGGER.info(f"   HTTP port: {self.http_port}, RTSP port: {self.rtsp_port}")

    async def async_test_connection(self) -> bool:
        """Test connection to device using hello endpoint."""
        try:
            async with self.session.get(
                f"http://{self.host}:{self.http_port}/cgi-bin/hello",
                auth=self._auth,
                timeout=5
            ) as response:
                self._available = response.status == 200
                if self._available:
                    _LOGGER.info(f"✅ Connected to Vivotek SD9364-EHL at {self.host}")
                return self._available
        except Exception as err:
            _LOGGER.error(f"❌ Failed to connect to Vivotek: {err}")
            self._available = False
            return False

    async def async_get_snapshot(self) -> Optional[bytes]:
        """Get snapshot from Vivotek camera via RTSP (most reliable method)."""
        try:
            _LOGGER.info("📸 Getting snapshot via RTSP")
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
            
            # Команда ffmpeg для получения одного кадра из RTSP потока
            rtsp_url = f"rtsp://{self.username}:{self.password}@{self.host}:{self.rtsp_port}/live.sdp"
            cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-frames:v", "1",
                "-f", "image2",
                "-y",
                tmp_path
            ]
            
            _LOGGER.debug(f"Running ffmpeg: {' '.join(cmd)}")
            
            # Запускаем ffmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Читаем полученный файл
                async with aiofiles.open(tmp_path, 'rb') as f:
                    data = await f.read()
                
                # Удаляем временный файл
                try:
                    os.unlink(tmp_path)
                except:
                    pass
                
                if len(data) > 1000:
                    _LOGGER.info(f"✅ Snapshot via RTSP successful ({len(data)} bytes)")
                    return data
                else:
                    _LOGGER.warning(f"Snapshot too small: {len(data)} bytes")
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                _LOGGER.error(f"❌ FFmpeg error: {error_msg[:200]}")
                
        except Exception as err:
            _LOGGER.error(f"❌ RTSP snapshot failed: {err}")
        
        # Если RTSP не сработал, пробуем HTTP (для отладки)
        _LOGGER.info("Trying HTTP snapshot as fallback")
        try:
            url = f"http://{self.host}:{self.http_port}/cgi-bin/viewer/video.mjpg"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    data = await response.read()
                    if len(data) > 1000:
                        _LOGGER.info(f"✅ HTTP snapshot successful ({len(data)} bytes)")
                        return data
        except Exception as err:
            _LOGGER.debug(f"HTTP snapshot failed: {err}")
        
        _LOGGER.error("❌ All Vivotek snapshot attempts failed")
        return None

    def get_rtsp_url(self, stream: int = 1) -> str:
        """Get RTSP URL for specified stream (1-4)."""
        if stream not in self.rtsp_streams:
            stream = 1
        return f"rtsp://{self.username}:{self.password}@{self.host}:{self.rtsp_port}/{self.rtsp_streams[stream]}"

    def get_mjpeg_url(self, stream: int = 1) -> str:
        """Get MJPEG URL for specified stream (1-4)."""
        if stream not in self.http_streams:
            stream = 1
        return f"http://{self.username}:{self.password}@{self.host}:{self.http_port}/cgi-bin/viewer/{self.http_streams[stream]}"

    @property
    def snapshot_url(self) -> str:
        """Get snapshot URL (for compatibility)."""
        return f"rtsp://{self.username}:{self.password}@{self.host}:{self.rtsp_port}/live.sdp"

    @property
    def mjpeg_url(self) -> str:
        """Get MJPEG stream URL for main stream."""
        return self.get_mjpeg_url(1)

    @property
    def rtsp_url_main(self) -> str:
        """Get main RTSP stream URL."""
        return self.get_rtsp_url(1)

    @property
    def rtsp_url_sub(self) -> str:
        """Get sub RTSP stream URL (stream 2)."""
        return self.get_rtsp_url(2)

    @property
    def is_available(self) -> bool:
        """Return True if device is available."""
        return self._available

    @property
    def model_name(self) -> str:
        """Get camera model name."""
        return "SD9364-EHL"

    @property
    def firmware_version(self) -> str:
        """Get firmware version."""
        return "SD9364-VVTK-0109a"

    @property
    def serial_number(self) -> str:
        """Get serial number."""
        return "0002D14F61AE"

    @property
    def state(self) -> Dict[str, Any]:
        """Return current device state."""
        return {
            "online": self._available,
            "host": self.host,
            "camera_name": self.camera_name,
            "model": self.model_name,
            "firmware": self.firmware_version,
            "serial": self.serial_number,
            "rtsp_port": self.rtsp_port,
            "http_port": self.http_port,
        }
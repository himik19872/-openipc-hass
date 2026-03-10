"""PTZ control for Vivotek cameras."""
import logging
import aiohttp
from typing import Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

class VivotekPTZ:
    """PTZ control for Vivotek SD9364-EHL camera."""

    def __init__(self, hass: HomeAssistant, host: str, username: str, password: str):
        """Initialize PTZ control."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.session = async_get_clientsession(hass)
        self._auth = aiohttp.BasicAuth(username, password)
        
        # Параметры из конфигурации камеры
        self._pan_range = [0, 22399]  # 0-360 градусов
        self._tilt_range = [0, 6845]  # -20 до +90 градусов
        self._zoom_range = [0, 16384]  # 0-30x оптический зум
        
        # Текущие позиции
        self._current_pan = 0
        self._current_tilt = 0
        self._current_zoom = 0
        
        # Пресеты
        self._presets = {}
        
        _LOGGER.info(f"✅ PTZ initialized for Vivotek SD9364-EHL at {host}")

    async def async_move(self, direction: str, speed: int = 50) -> bool:
        """
        Move camera in direction.
        Directions: up, down, left, right, up-left, up-right, down-left, down-right
        Also supports: in, out for zoom
        Speed: 0-100
        """
        _LOGGER.info(f"🎯 Moving {direction} at speed {speed}")
        
        # Конвертируем скорость в формат камеры (0-127)
        cam_speed = int(speed * 127 / 100)
        
        # Определяем параметры движения
        pan = 0
        tilt = 0
        zoom = 0
        
        # Обработка зума
        if direction == "in":
            _LOGGER.info("🔍 Zooming in")
            zoom = cam_speed
        elif direction == "out":
            _LOGGER.info("🔍 Zooming out")
            zoom = -cam_speed
        # Обработка движения
        else:
            if 'left' in direction:
                pan = -cam_speed
            elif 'right' in direction:
                pan = cam_speed
                
            if 'up' in direction:
                tilt = cam_speed
            elif 'down' in direction:
                tilt = -cam_speed
        
        # Отправляем команду
        return await self._send_command("move", pan, tilt, zoom)

    async def async_zoom(self, direction: str, speed: int = 50) -> bool:
        """Zoom in/out (для совместимости)."""
        return await self.async_move(direction, speed)

    async def async_stop(self) -> bool:
        """Stop all movement."""
        _LOGGER.info("🛑 Stopping PTZ movement")
        return await self._send_command("stop")

    async def async_goto_preset(self, preset_id: int) -> bool:
        """Go to preset position."""
        _LOGGER.info(f"📍 Going to preset {preset_id}")
        return await self._send_command("goto", preset=preset_id)

    async def async_set_preset(self, preset_id: int, name: str = "") -> bool:
        """Set current position as preset."""
        _LOGGER.info(f"📍 Setting preset {preset_id}: {name}")
        return await self._send_command("setpreset", preset=preset_id, name=name)

    async def async_get_presets(self) -> Dict[int, str]:
        """Get all presets."""
        try:
            url = f"http://{self.host}/cgi-bin/camctrl/camctrl.cgi?getpreset=1"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    text = await response.text()
                    _LOGGER.debug(f"Presets response: {text}")
                    
                    # Парсим пресеты
                    presets = {}
                    lines = text.strip().split('\n')
                    for line in lines:
                        if '=' in line and 'PresetName' in line:
                            parts = line.split('=')
                            if len(parts) == 2:
                                preset_num = parts[0].replace('PresetName', '')
                                try:
                                    preset_id = int(preset_num)
                                    presets[preset_id] = parts[1]
                                except:
                                    pass
                    
                    self._presets = presets
                    return presets
        except Exception as err:
            _LOGGER.debug(f"Error getting presets: {err}")
        
        return self._presets

    async def _send_command(self, cmd_type: str, pan: int = 0, tilt: int = 0, 
                            zoom: int = 0, preset: int = None, name: str = None) -> bool:
        """Send PTZ command to camera."""
        try:
            if cmd_type == "move":
                url = (f"http://{self.host}/cgi-bin/camctrl/camctrl.cgi?"
                      f"move=1&pan={pan}&tilt={tilt}&zoom={zoom}&reserved1=0")
            
            elif cmd_type == "stop":
                url = f"http://{self.host}/cgi-bin/camctrl/camctrl.cgi?stop=1"
            
            elif cmd_type == "goto" and preset is not None:
                url = (f"http://{self.host}/cgi-bin/camctrl/camctrl.cgi?"
                      f"gotopreset=1&presetno={preset}")
            
            elif cmd_type == "setpreset" and preset is not None:
                url = (f"http://{self.host}/cgi-bin/camctrl/camctrl.cgi?"
                      f"setpreset=1&presetno={preset}")
                if name:
                    url += f"&name={name}"
            
            else:
                _LOGGER.error(f"Invalid PTZ command: {cmd_type}")
                return False
            
            _LOGGER.debug(f"Sending PTZ command: {url}")
            
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                success = response.status == 200
                if success:
                    _LOGGER.debug(f"✅ PTZ command {cmd_type} successful")
                else:
                    text = await response.text()
                    _LOGGER.error(f"❌ PTZ command failed: HTTP {response.status}")
                return success
                
        except Exception as err:
            _LOGGER.error(f"Error sending PTZ command: {err}")
            return False
"""Beward device support for OpenIPC integration."""
import logging
import aiohttp
import asyncio
import base64
import re
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
        self._firmware = None
        self._hardware = None
        self._serial = None
        self._uptime = None
        
        self._state = {
            "online": False,
            "volume": 100,
            "last_motion": None,
            "last_door_open": None,
            "last_break_in": None,
            "temperature": None,
            "relay_1_state": False,
            "relay_2_state": False,
            "motion_detected": False,
            "door_open": False,
            "break_in_detected": False,
            "uptime_seconds": 0,
        }
        
        self._audio_config = {
            "audio_switch": "open",
            "audio_type": "G.711A",
            "audio_out_vol": 15,
            "audio_in_vol": 8,
            "echo_cancellation": "open",
        }
        
        # Правильные эндпоинты из документации Beward
        self._endpoints = {
            # Audio endpoints (раздел 3.6 и 12)
            "audio_transmit": "/cgi-bin/audio/transmit.cgi",
            "audio_set": "/cgi-bin/audio_cgi?action=set",
            "audio_get": "/cgi-bin/audio_cgi?action=get",
            
            # Snapshot endpoints (раздел 4)
            "snapshot": "/cgi-bin/jpg/image.cgi",
            "snapshot_alt": "/cgi-bin/snapshot.cgi",
            
            # Relay endpoints из документации ALARM OUT (раздел 40.1, стр. 130)
            "relay_1_on": "/cgi-bin/alarmout_cgi?action=set&Output=0&Status=1",
            "relay_1_off": "/cgi-bin/alarmout_cgi?action=set&Output=0&Status=0",
            "relay_2_on": "/cgi-bin/alarmout_cgi?action=set&Output=1&Status=1",
            "relay_2_off": "/cgi-bin/alarmout_cgi?action=set&Output=1&Status=0",
            "relay_all_close": "/cgi-bin/alarmout_cgi?action=set&Output=0&Status=2",
            "relay_status": "/cgi-bin/alarmout_cgi?action=status",
            
            # System endpoints
            "system_info": "/cgi-bin/systeminfo_cgi",
            "status": "/cgi-bin/status.cgi",
            "alarm_status": "/cgi-bin/alarmstate_cgi?action=get",
            
            # Альтернативные эндпоинты на всякий случай
            "controller": "/cgi-bin/controller_cgi",
        }
        
        # Сохраняем рабочие эндпоинты после обнаружения
        self._working_endpoints = {
            "relay_1_on": None,
            "relay_1_off": None,
            "relay_2_on": None,
            "relay_2_off": None,
        }
        
        # Состояния
        self.door_open = False
        self.motion_detected = False
        self.break_in_detected = False
        self.network_ok = True
        
        _LOGGER.info(f"✅ Beward device initialized for {camera_name} at {host}")

    async def async_connect(self) -> bool:
        """Connect to Beward device."""
        _LOGGER.info(f"🔧 Connecting to Beward at {self.host}")
        try:
            # Проверяем доступность через systeminfo
            url = f"http://{self.host}{self._endpoints['system_info']}"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    text = await response.text()
                    self._parse_system_info(text)
                    
                    self._available = True
                    self._state["online"] = True
                    self.network_ok = True
                    _LOGGER.info(f"✅ Connected to Beward {self._model} (FW: {self._firmware})")
                    
                    # Загружаем аудио конфигурацию
                    await self._async_update_audio_config()
                    
                    # Проверяем эндпоинты для реле
                    await self._verify_relay_endpoints()
                    
                    # Проверяем RTSP поток после подключения
                    self.hass.async_create_task(self.async_check_rtsp())
                    return True
                else:
                    _LOGGER.error(f"❌ Failed to connect to Beward: HTTP {response.status}")
                    return False
        except Exception as err:
            _LOGGER.error(f"❌ Error connecting to Beward: {err}")
            self._available = False
            self.network_ok = False
            return False

    async def _verify_relay_endpoints(self):
        """Verify relay endpoints work."""
        _LOGGER.info("🔍 Verifying Beward relay endpoints...")
        
        relay_endpoints = [
            ("relay_1_on", self._endpoints["relay_1_on"]),
            ("relay_1_off", self._endpoints["relay_1_off"]),
            ("relay_2_on", self._endpoints["relay_2_on"]),
            ("relay_2_off", self._endpoints["relay_2_off"]),
        ]
        
        for key, endpoint in relay_endpoints:
            url = f"http://{self.host}{endpoint}"
            try:
                _LOGGER.debug(f"Testing endpoint: {url}")
                async with self.session.get(url, auth=self._auth, timeout=2) as response:
                    if response.status == 200:
                        self._working_endpoints[key] = endpoint
                        _LOGGER.info(f"✅ Relay endpoint working: {endpoint}")
                    else:
                        _LOGGER.debug(f"Endpoint {endpoint} returned HTTP {response.status}")
            except Exception as e:
                _LOGGER.debug(f"Endpoint {endpoint} failed: {e}")
        
        # Проверяем, что все эндпоинты работают
        required = ["relay_1_on", "relay_1_off", "relay_2_on", "relay_2_off"]
        missing = [r for r in required if not self._working_endpoints.get(r)]
        if missing:
            _LOGGER.warning(f"⚠️ Some relay endpoints not working: {missing}")
        else:
            _LOGGER.info("✅ All relay endpoints verified")

    async def async_update(self) -> Dict[str, Any]:
        """Update device state."""
        try:
            # Получаем статус
            url = f"http://{self.host}{self._endpoints['status']}"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    text = await response.text()
                    self._parse_status(text)
            
            # Получаем статус тревог
            url = f"http://{self.host}{self._endpoints['alarm_status']}"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    text = await response.text()
                    self._parse_alarm_status(text)
            
            return self._state.copy()
        except Exception as err:
            _LOGGER.error(f"Error updating Beward state: {err}")
            return self._state.copy()

    def _parse_system_info(self, text: str):
        """Parse system info response."""
        fw_match = re.search(r'SoftwareVersion=([^\n\r]+)', text)
        if fw_match:
            self._firmware = fw_match.group(1).strip()
        
        hw_match = re.search(r'HardwareVersion=([^\n\r]+)', text)
        if hw_match:
            self._hardware = hw_match.group(1).strip()
        
        model_match = re.search(r'DeviceModel=([^\n\r]+)', text)
        if model_match:
            self._model = model_match.group(1).strip()
        
        uuid_match = re.search(r'DeviceUUID=([^\n\r]+)', text)
        if uuid_match:
            self._serial = uuid_match.group(1).strip()
        
        uptime_match = re.search(r'UpTime=([^\n\r]+)', text)
        if uptime_match:
            self._uptime = uptime_match.group(1).strip()
            parts = self._uptime.split(':')
            if len(parts) == 3:
                self._state["uptime_seconds"] = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    def _parse_status(self, text: str):
        """Parse status response."""
        temp_match = re.search(r'CPU Temp\s*:\s*([0-9.]+)', text, re.IGNORECASE)
        if temp_match:
            try:
                self._state["temperature"] = float(temp_match.group(1))
            except:
                pass
        
        model_match = re.search(r'Model\s*:\s*([^\n\r]+)', text, re.IGNORECASE)
        if model_match:
            self._model = model_match.group(1).strip()

    def _parse_alarm_status(self, text: str):
        """Parse alarm status response."""
        if 'MotionDetection' in text and 'Alarm Status=1' in text:
            self.motion_detected = True
            self._state["motion_detected"] = True
            self._state["last_motion"] = datetime.now().isoformat()
        else:
            self.motion_detected = False
            self._state["motion_detected"] = False
        
        if 'SensorAlarm' in text and 'Alarm Status=1' in text:
            self.door_open = True
            self._state["door_open"] = True
            self._state["last_door_open"] = datetime.now().isoformat()
        else:
            self.door_open = False
            self._state["door_open"] = False

    async def _async_update_audio_config(self):
        """Update audio configuration."""
        try:
            url = f"http://{self.host}{self._endpoints['audio_get']}"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    text = await response.text()
                    self._parse_audio_config(text)
        except Exception as err:
            _LOGGER.debug(f"Failed to update audio config: {err}")

    def _parse_audio_config(self, text: str):
        """Parse audio configuration."""
        switch_match = re.search(r'AudioSwitch=(\w+)', text)
        if switch_match:
            self._audio_config["audio_switch"] = switch_match.group(1)
        
        type_match = re.search(r'AudioType=([^\n\r]+)', text)
        if type_match:
            self._audio_config["audio_type"] = type_match.group(1).strip()
        
        in_vol_match = re.search(r'AudioInVol=(\d+)', text)
        if in_vol_match:
            self._audio_config["audio_in_vol"] = int(in_vol_match.group(1))
        
        out_vol_match = re.search(r'AudioOutVol=(\d+)', text)
        if out_vol_match:
            self._audio_config["audio_out_vol"] = int(out_vol_match.group(1))
            self._state["volume"] = int(out_vol_match.group(1)) * 100 // 15
        
        echo_match = re.search(r'EchoCancellation=(\w+)', text)
        if echo_match:
            self._audio_config["echo_cancellation"] = echo_match.group(1)

    async def async_disconnect(self):
        """Disconnect from Beward device."""
        _LOGGER.info(f"🔧 Disconnecting from Beward at {self.host}")
        self._available = False
        self.network_ok = False
        _LOGGER.info("✅ Beward disconnected")

    async def async_check_rtsp(self) -> bool:
        """Check if RTSP stream is available."""
        try:
            import subprocess
            cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-i", self.rtsp_url_main,
                "-t", "1",
                "-f", "null",
                "-"
            ]
            _LOGGER.debug(f"Checking RTSP stream: {self.rtsp_url_main}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            success = process.returncode == 0
            
            if success:
                _LOGGER.info(f"✅ RTSP stream available for Beward at {self.host}")
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                _LOGGER.warning(f"❌ RTSP stream not available for Beward at {self.host}: {error_msg[:200]}")
            
            return success
        except Exception as err:
            _LOGGER.error(f"RTSP check failed: {err}")
            return False

    async def async_set_relay(self, relay_id: int = 1, state: bool = True) -> bool:
        """Set relay state (on/off) using endpoints from documentation."""
        try:
            # Используем эндпоинты из документации
            if relay_id == 1:
                endpoint = self._endpoints["relay_1_on"] if state else self._endpoints["relay_1_off"]
            else:
                endpoint = self._endpoints["relay_2_on"] if state else self._endpoints["relay_2_off"]
            
            url = f"http://{self.host}{endpoint}"
            _LOGGER.info(f"🔌 Setting Beward relay {relay_id} to {'ON' if state else 'OFF'}")
            _LOGGER.debug(f"URL: {url}")
            
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                _LOGGER.debug(f"Response status: {response.status}")
                
                if response.status == 200:
                    try:
                        text = await response.text()
                        _LOGGER.debug(f"Response body: {text[:200]}")
                    except:
                        pass
                    
                    self._state[f"relay_{relay_id}_state"] = state
                    _LOGGER.info(f"✅ Beward relay {relay_id} {'activated' if state else 'deactivated'}")
                    
                    # Если это включение, планируем автоматическое выключение через 1 секунду
                    if state:
                        async def auto_off():
                            await asyncio.sleep(1)
                            await self.async_set_relay(relay_id, False)
                        
                        asyncio.create_task(auto_off())
                    
                    return True
                else:
                    _LOGGER.error(f"❌ Failed to set Beward relay {relay_id}: HTTP {response.status}")
                    return False
        except Exception as err:
            _LOGGER.error(f"❌ Error setting Beward relay {relay_id}: {err}")
            return False

    async def async_open_door(self, main: bool = True) -> bool:
        """Open door (activate relay briefly)."""
        _LOGGER.info(f"🚪 Opening {'main' if main else 'secondary'} door on Beward")
        
        relay_id = 1 if main else 2
        success = await self.async_set_relay(relay_id, True)
        
        if success:
            self.door_open = True
            self._state["door_open"] = True
            self._state["last_door_open"] = datetime.now().isoformat()
        
        return success

    async def _send_audio_data(self, audio_data: bytes) -> bool:
        """Send audio data to camera according to Beward API spec (section 3.6)."""
        try:
            headers = {
                "Content-Type": "audio/basic",  # audio/basic для G.711 μ-law
                "Authorization": f"Basic {self.auth_base64}",
                "Connection": "Keep-Alive",
                "Cache-Control": "no-cache",
                "Content-Length": str(len(audio_data))
            }
            
            url = f"http://{self.host}{self._endpoints['audio_transmit']}"
            _LOGGER.info(f"🔊 Sending {len(audio_data)} bytes to Beward at {url}")
            _LOGGER.debug(f"Headers: {headers}")
            
            # Открываем соединение и отправляем данные
            connector = aiohttp.TCPConnector(force_close=True)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, headers=headers, data=audio_data, auth=self._auth, timeout=10) as response:
                    _LOGGER.debug(f"Response status: {response.status}")
                    
                    if response.status == 200:
                        _LOGGER.info(f"✅ Audio sent successfully to Beward")
                        return True
                    else:
                        _LOGGER.error(f"❌ Audio send failed: HTTP {response.status}")
                        try:
                            error_text = await response.text()
                            _LOGGER.debug(f"Beward response: {error_text[:200]}")
                        except:
                            pass
                        return False
                    
        except asyncio.TimeoutError:
            _LOGGER.error(f"❌ Audio send timeout")
            return False
        except Exception as err:
            _LOGGER.error(f"❌ Audio send failed: {err}")
            return False

    async def async_play_beep(self) -> bool:
        """Play beep sound."""
        _LOGGER.info("🔊 Playing beep on Beward")
        audio_data = bytes([0x80] * 4000)  # 0.5 секунды тишины
        return await self._send_audio_data(audio_data)

    async def async_play_ding(self) -> bool:
        """Play ding sound."""
        _LOGGER.info("🔊 Playing ding on Beward")
        audio_data = bytes([0x80] * 8000)  # 1 секунда тишины
        return await self._send_audio_data(audio_data)

    async def async_play_doorbell(self) -> bool:
        """Play doorbell sound."""
        _LOGGER.info("🔊 Playing doorbell on Beward")
        return await self.async_play_beep()

    async def async_play_tts(self, tts_data: bytes) -> bool:
        """Play TTS audio data on Beward."""
        _LOGGER.info(f"🔊 Playing TTS on Beward ({len(tts_data)} bytes)")
        return await self._send_audio_data(tts_data)

    async def async_set_volume(self, volume: int) -> bool:
        """Set volume (0-100)."""
        _LOGGER.info(f"🔊 Setting Beward volume to {volume}%")
        out_vol = max(1, min(15, volume * 15 // 100))
        self._audio_config["audio_out_vol"] = out_vol
        self._state["volume"] = volume
        
        try:
            url = f"http://{self.host}{self._endpoints['audio_set']}&AudioOutVol={out_vol}"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                return response.status == 200
        except:
            return True

    async def async_enable_audio(self, enable: bool) -> bool:
        """Enable/disable audio."""
        _LOGGER.info(f"🔊 {'Enabling' if enable else 'Disabling'} audio on Beward")
        switch = "open" if enable else "close"
        self._audio_config["audio_switch"] = switch
        
        try:
            url = f"http://{self.host}{self._endpoints['audio_set']}&AudioSwitch={switch}"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                return response.status == 200
        except:
            return True

    async def async_get_snapshot(self) -> Optional[bytes]:
        """Get snapshot from Beward."""
        url = f"http://{self.host}{self._endpoints['snapshot']}"
        try:
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    data = await response.read()
                    _LOGGER.debug(f"✅ Snapshot captured from main endpoint: {len(data)} bytes")
                    return data
                else:
                    _LOGGER.debug(f"Main snapshot endpoint returned HTTP {response.status}")
        except Exception as err:
            _LOGGER.debug(f"Failed to get snapshot from main endpoint: {err}")
        
        try:
            url = f"http://{self.host}{self._endpoints['snapshot_alt']}"
            async with self.session.get(url, auth=self._auth, timeout=5) as response:
                if response.status == 200:
                    data = await response.read()
                    _LOGGER.debug(f"✅ Snapshot captured from alt endpoint: {len(data)} bytes")
                    return data
        except Exception as err:
            _LOGGER.debug(f"Failed to get snapshot from alt endpoint: {err}")
        
        _LOGGER.error("❌ Failed to get snapshot from Beward")
        return None

    async def async_test_alarm(self) -> Dict[str, Any]:
        """Test alarm functions."""
        results = {}
        
        _LOGGER.info("Testing Beward relay 1...")
        results["relay1_on"] = await self.async_set_relay(1, True)
        await asyncio.sleep(0.5)
        results["relay1_off"] = await self.async_set_relay(1, False)
        
        _LOGGER.info("Testing Beward relay 2...")
        results["relay2_on"] = await self.async_set_relay(2, True)
        await asyncio.sleep(0.5)
        results["relay2_off"] = await self.async_set_relay(2, False)
        
        _LOGGER.info("Testing Beward audio...")
        results["beep"] = await self.async_play_beep()
        
        return results

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
    def firmware(self) -> Optional[str]:
        return self._firmware

    @property
    def hardware(self) -> Optional[str]:
        return self._hardware

    @property
    def serial(self) -> Optional[str]:
        return self._serial

    @property
    def rtsp_url_main(self) -> str:
        return f"rtsp://{self.username}:{self.password}@{self.host}:554/av0_0"

    @property
    def rtsp_url_sub(self) -> str:
        return f"rtsp://{self.username}:{self.password}@{self.host}:554/av0_1"

    def async_write_ha_state(self):
        """Mock method for closing door."""
        pass
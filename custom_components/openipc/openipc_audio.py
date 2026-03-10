"""OpenIPC audio handling for TTS."""
import logging
import subprocess
import os
from typing import Optional
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class OpenIPCAudio:
    """Class to handle audio playback on OpenIPC cameras."""

    def __init__(self, hass: HomeAssistant, host: str, username: str, password: str, coordinator=None):
        """Initialize OpenIPC audio."""
        self.hass = hass
        self.host = host
        self.username = username
        self.password = password
        self.coordinator = coordinator
        self._available = False

    async def async_test_connection(self) -> bool:
        """Test connection to audio endpoint."""
        try:
            import aiohttp
            auth = aiohttp.BasicAuth(self.username, self.password)
            url = f"http://{self.host}/play_audio"
            
            async with aiohttp.ClientSession() as session:
                async with session.head(url, auth=auth, timeout=5) as response:
                    self._available = response.status in [200, 401]
                    return self._available
        except Exception as err:
            _LOGGER.debug("OpenIPC audio endpoint not available: %s", err)
            self._available = False
            return False

    async def async_play_pcm(self, pcm_file_path: str) -> bool:
        """Play PCM file on OpenIPC camera."""
        if not os.path.exists(pcm_file_path):
            _LOGGER.error("PCM file not found: %s", pcm_file_path)
            return False

        _LOGGER.info("🔊 Playing PCM file on OpenIPC camera: %s", pcm_file_path)
        
        return await self.hass.async_add_executor_job(
            self._play_pcm_sync, pcm_file_path
        )

    def _play_pcm_sync(self, pcm_file_path: str) -> bool:
        """Synchronous method to play PCM using curl."""
        import subprocess
        
        url = f"http://{self.host}/play_audio"
        cmd = [
            "curl", "-s", "-u", f"{self.username}:{self.password}",
            "--data-binary", f"@{pcm_file_path}",
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                _LOGGER.info("✅ PCM played successfully on OpenIPC camera")
                return True
            else:
                _LOGGER.error("❌ Failed to play PCM: %s", result.stderr)
                return False
        except subprocess.TimeoutExpired:
            _LOGGER.error("Timeout playing PCM")
            return False
        except Exception as e:
            _LOGGER.error("Error playing PCM: %s", e)
            return False

    async def async_generate_and_play_tts(self, message: str, language: str = "ru") -> bool:
        """
        Generate TTS using gTTS (via add-on or locally) and play it.
        Returns True if successful, False otherwise.
        """
        # Сначала пробуем использовать аддон
        if self.coordinator and self.coordinator.use_addon and self.coordinator.addon.available:
            try:
                _LOGGER.info(f"Using add-on for TTS: '{message}'")
                camera_name = self.coordinator.recorder.camera_name if hasattr(self.coordinator, 'recorder') else "camera"
                
                # Отправляем TTS через addon
                success = await self.coordinator.addon.async_tts(camera_name, message, language)
                if success:
                    _LOGGER.info("✅ TTS via add-on successful")
                    return True
                else:
                    _LOGGER.warning("Add-on TTS failed, falling back to local")
            except Exception as err:
                _LOGGER.error(f"Add-on TTS error: {err}, falling back to local")
        
        # Fallback на локальный метод
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as tmp:
            pcm_path = tmp.name
        
        try:
            success = await self.hass.async_add_executor_job(
                self._generate_tts_sync, message, language, pcm_path
            )
            
            if not success:
                _LOGGER.error("Failed to generate TTS locally")
                return False
            
            return await self.async_play_pcm(pcm_path)
            
        finally:
            if os.path.exists(pcm_path):
                os.unlink(pcm_path)

    def _generate_tts_sync(self, message: str, language: str, output_path: str) -> bool:
        """Synchronous method to generate TTS using gTTS and convert to PCM."""
        import subprocess
        import tempfile
        
        temp_mp3 = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
        
        try:
            python_cmd = f"""
import sys
try:
    from gtts import gTTS
    tts = gTTS(text='''{message}''', lang='{language}', slow=False)
    tts.save('{temp_mp3}')
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {{e}}")
    sys.exit(1)
"""
            result = subprocess.run(
                ["python3", "-c", python_cmd],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                _LOGGER.error("gTTS error: %s", result.stderr)
                return False
            
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", temp_mp3,
                "-ar", "8000", "-ac", "1", "-f", "s16le",
                output_path
            ]
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                _LOGGER.error("ffmpeg error: %s", result.stderr)
                return False
            
            return True
            
        except Exception as e:
            _LOGGER.error("Error generating TTS: %s", e)
            return False
            
        finally:
            if os.path.exists(temp_mp3):
                os.unlink(temp_mp3)

    @property
    def is_available(self) -> bool:
        """Return True if audio endpoint is available."""
        return self._available
        
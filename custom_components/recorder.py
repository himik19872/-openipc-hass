"""Video recorder for OpenIPC integration."""
import os
import logging
import asyncio
import aiohttp
import aiofiles
import time
from datetime import datetime
from pathlib import Path
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Попытка импортировать PIL для работы с изображениями
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    _LOGGER = logging.getLogger(__name__)
    _LOGGER.warning("PIL not available. Please install: pip install Pillow")

from .const import DOMAIN, OSD_POSITIONS

_LOGGER = logging.getLogger(__name__)

class OpenIPCRecorder:
    """Class to handle video recording to HA media folder."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, username: str, password: str, camera_name: str):
        """Initialize recorder."""
        self.hass = hass
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.camera_name = camera_name.replace(" ", "_").lower()
        self.session = async_get_clientsession(hass)
        self.auth = aiohttp.BasicAuth(username, password)
        
        # Базовая папка media в Home Assistant
        self.media_base = Path(hass.config.path("media"))
        # Создаем папку для конкретной камеры
        self.record_folder = self.media_base / "openipc_recordings" / self.camera_name
        
        # Папка со шрифтами ВНУТРИ интеграции
        self.fonts_folder = Path(hass.config.path("custom_components/openipc/openipc_fonts"))
        
        # Создаем папку для шрифтов, если её нет
        self.hass.async_create_task(self._ensure_fonts_folder_exists())
        
        # Создаем папку для записей, если её нет
        self.hass.async_create_task(self._ensure_folder_exists_async())
        
        if not PIL_AVAILABLE:
            _LOGGER.error("PIL not available. OSD will not work. Please install Pillow")
        
        _LOGGER.info("Recorder initialized for %s, saving to %s", camera_name, self.record_folder)
        _LOGGER.info("Fonts folder (internal): %s", self.fonts_folder)

    async def _ensure_fonts_folder_exists(self):
        """Ensure fonts folder exists inside integration."""
        try:
            await asyncio.to_thread(self.fonts_folder.mkdir, parents=True, exist_ok=True)
            _LOGGER.debug("Fonts folder ensured: %s", self.fonts_folder)
            
            # Проверим, есть ли там шрифты
            font_files = await self._get_font_files()
            if font_files:
                _LOGGER.info(f"✅ Found {len(font_files)} font files in integration folder")
                for font in font_files[:5]:
                    _LOGGER.debug(f"  - {font}")
            else:
                _LOGGER.warning(f"⚠️ No font files found in {self.fonts_folder}")
                _LOGGER.info("Please add .ttf files to: /config/custom_components/openipc/openipc_fonts/")
                
        except Exception as err:
            _LOGGER.error("Failed to create fonts folder: %s", err)

    async def _get_font_files(self) -> list:
        """Get list of font files in the integration fonts folder."""
        try:
            if not await asyncio.to_thread(self.fonts_folder.exists):
                return []
            
            files = await asyncio.to_thread(
                lambda: [f.name for f in self.fonts_folder.glob("*.ttf")] + 
                        [f.name for f in self.fonts_folder.glob("*.TTF")]
            )
            return sorted(files)
        except Exception as err:
            _LOGGER.error("Error getting font files: %s", err)
            return []

    async def list_available_fonts(self) -> list:
        """List all available fonts in the integration fonts folder."""
        font_files = await self._get_font_files()
        
        _LOGGER.info(f"📚 Available fonts in integration folder ({self.fonts_folder}):")
        if font_files:
            for i, font in enumerate(font_files, 1):
                _LOGGER.info(f"  {i}. {font}")
        else:
            _LOGGER.info("  No fonts found")
            _LOGGER.info("  Please add .ttf files to: /config/custom_components/openipc/openipc_fonts/")
        
        return font_files

    def _get_telegram_config(self):
        """Get Telegram configuration from hass.data."""
        config = self.hass.data.get(DOMAIN, {}).get("config", {})
        _LOGGER.debug("Raw config from hass.data: %s", config)
        
        bot_token = config.get("telegram_bot_token")
        chat_id = config.get("telegram_chat_id")
        
        # Преобразуем chat_id в строку, если это число
        if chat_id is not None:
            chat_id = str(chat_id)
        
        _LOGGER.debug("Extracted telegram config: bot_token=%s, chat_id=%s", 
                     "✅" if bot_token else "❌", chat_id or "❌")
        
        return {
            "bot_token": bot_token,
            "chat_id": chat_id
        }

    async def _ensure_folder_exists_async(self):
        """Ensure record folder exists asynchronously."""
        try:
            await asyncio.to_thread(self.record_folder.mkdir, parents=True, exist_ok=True)
            _LOGGER.debug("Record folder ensured: %s", self.record_folder)
        except Exception as err:
            _LOGGER.error("Failed to create record folder: %s", err)

    def _generate_filename(self, duration: int = None) -> str:
        """Generate filename with camera name and timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if duration:
            return f"{self.camera_name}_{timestamp}_{duration}s.mp4"
        return f"{self.camera_name}_{timestamp}.mp4"

    async def _get_osd_values(self) -> dict:
        """Get current values for OSD placeholders."""
        # Получаем данные из координатора
        if self.hass.data.get(DOMAIN):
            for entry_id, coordinator in self.hass.data[DOMAIN].items():
                if entry_id == "config":
                    continue
                if hasattr(coordinator, 'data') and coordinator.data:
                    parsed = coordinator.data.get("parsed", {})
                    
                    # Формируем значения для OSD
                    values = {
                        "camera_name": self.camera_name,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "cpu_temp": parsed.get("cpu_temp", "N/A"),
                        "uptime": parsed.get("uptime", "N/A"),
                        "fps": parsed.get("fps", "N/A"),
                        "bitrate": parsed.get("bitrate", "N/A"),
                        "resolution": parsed.get("resolution", "N/A"),
                        "wifi_signal": parsed.get("wifi_signal", "N/A"),
                        "motion": "Active" if parsed.get("motion_detected") else "Inactive",
                        "recording": "Yes" if parsed.get("recording_status") else "No",
                    }
                    return values
        
        # Если данные не получены, возвращаем базовые значения
        return {
            "camera_name": self.camera_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_temp": "N/A",
            "uptime": "N/A",
            "fps": "N/A",
            "bitrate": "N/A",
            "resolution": "N/A",
            "wifi_signal": "N/A",
            "motion": "Unknown",
            "recording": "Unknown",
        }

    async def _add_text_to_image(self, image_path: Path, lines: list, osd_config: dict):
        """Add text to image using fonts from integration folder."""
        try:
            # Открываем изображение
            img = await asyncio.to_thread(Image.open, image_path)
            
            # Конвертируем в RGB если нужно
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            draw = await asyncio.to_thread(ImageDraw.Draw, img)
            
            # Получаем параметры из osd_config
            position = osd_config.get('position', 'top_left')
            # Увеличиваем размер шрифта в 5 раз
            base_font_size = int(osd_config.get('font_size', 24))
            font_size = base_font_size * 5
            
            _LOGGER.info(f"Font size: base={base_font_size}, multiplied={font_size}")
            
            color = osd_config.get('color', 'white')
            font_name = osd_config.get('font', 'default')
            
            # Преобразуем цвет в RGB
            color_map = {
                'white': (255, 255, 255),
                'black': (0, 0, 0),
                'red': (255, 0, 0),
                'green': (0, 255, 0),
                'blue': (0, 0, 255),
                'yellow': (255, 255, 0),
                'cyan': (0, 255, 255),
                'magenta': (255, 0, 255),
                'orange': (255, 165, 0),
                'purple': (128, 0, 128),
                'gray': (128, 128, 128),
            }
            rgb_color = color_map.get(color.lower(), (255, 255, 255))
            
            # Получаем размеры изображения
            img_width, img_height = img.size
            _LOGGER.info(f"Image size: {img_width}x{img_height}")
            
            # Путь к папке со шрифтами ВНУТРИ ИНТЕГРАЦИИ
            fonts_dir = self.fonts_folder
            _LOGGER.info(f"Looking for fonts in integration folder: {fonts_dir}")
            
            # Проверяем существование папки
            if not await asyncio.to_thread(fonts_dir.exists):
                _LOGGER.error(f"Fonts directory does not exist: {fonts_dir}")
                await asyncio.to_thread(fonts_dir.mkdir, parents=True, exist_ok=True)
                _LOGGER.info(f"Created fonts directory: {fonts_dir}")
                return
                
            # Получаем список шрифтов
            font_files = await self._get_font_files()
            
            if not font_files:
                _LOGGER.error(f"No font files found in {fonts_dir}")
                _LOGGER.info("Please download fonts to: /config/custom_components/openipc/openipc_fonts/")
                _LOGGER.info("You can download from: https://github.com/dejavu-fonts/dejavu-fonts")
                return
                
            _LOGGER.info(f"Found {len(font_files)} font files in integration")
            
            # Выбираем шрифт
            font_path = None
            
            # Если указан конкретный шрифт в конфиге
            if font_name != 'default':
                for f in font_files:
                    if font_name.lower() in f.lower():
                        font_path = fonts_dir / f
                        _LOGGER.info(f"Found requested font: {f}")
                        break
            
            # Если не нашли конкретный или не указан, ищем по приоритету
            if font_path is None:
                # Предпочитаемые шрифты в порядке приоритета
                preferred_fonts = [
                    "DejaVuSans.ttf",
                    "LiberationSans-Regular.ttf",
                    "OpenSans-Regular.ttf",
                    "Roboto-Regular.ttf",
                    "Arial.ttf",
                    "FreeSans.ttf",
                ]
                
                for pref_font in preferred_fonts:
                    for f in font_files:
                        if f == pref_font:
                            font_path = fonts_dir / f
                            _LOGGER.info(f"Using preferred font: {f}")
                            break
                    if font_path:
                        break
            
            # Если все еще не нашли, берем первый попавшийся
            if font_path is None and font_files:
                font_path = fonts_dir / font_files[0]
                _LOGGER.info(f"Using first available font: {font_files[0]}")
            
            if font_path is None:
                _LOGGER.error("No font files available")
                return
                
            # Загружаем шрифт
            try:
                font = ImageFont.truetype(str(font_path), font_size)
                _LOGGER.info(f"✅ Loaded font: {font_path.name} (size: {font_size})")
            except Exception as e:
                _LOGGER.error(f"Failed to load font {font_path.name}: {e}")
                # Пробуем загрузить с меньшим размером
                try:
                    font = ImageFont.truetype(str(font_path), 24)
                    _LOGGER.info(f"Loaded font with fallback size 24")
                except:
                    _LOGGER.error("Cannot load any font")
                    return
            
            # Вычисляем размеры текста
            line_heights = []
            line_widths = []
            
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                line_height = bbox[3] - bbox[1]
                line_widths.append(line_width)
                line_heights.append(line_height)
                _LOGGER.debug(f"Line '{line}': width={line_width}, height={line_height}")
            
            total_height = sum(line_heights) + 10 * (len(lines) - 1)
            max_width = max(line_widths)
            
            _LOGGER.info(f"Text block: width={max_width}, height={total_height}")
            
            # Вычисляем позицию
            padding = 20
            
            if position == "top_left":
                x = padding
                y = padding
            elif position == "top_right":
                x = img_width - max_width - padding
                y = padding
            elif position == "bottom_left":
                x = padding
                y = img_height - total_height - padding
            elif position == "bottom_right":
                x = img_width - max_width - padding
                y = img_height - total_height - padding
            elif position == "center":
                x = (img_width - max_width) // 2
                y = (img_height - total_height) // 2
            else:
                x = padding
                y = padding
            
            _LOGGER.info(f"Text position: x={x}, y={y}")
            
            # Рисуем текст
            current_y = y
            for i, line in enumerate(lines):
                bbox = draw.textbbox((x, current_y), line, font=font)
                expanded_bbox = (
                    bbox[0] - 10,
                    bbox[1] - 10,
                    bbox[2] + 10,
                    bbox[3] + 10
                )
                draw.rectangle(expanded_bbox, fill=(0, 0, 0, 220))
                
                draw.text((x, current_y), line, font=font, fill=rgb_color)
                
                current_y += line_heights[i] + 10
            
            await asyncio.to_thread(img.save, image_path)
            _LOGGER.info(f"✅ Text added to {image_path.name} using font {font_path.name} from integration")
            
        except Exception as err:
            _LOGGER.error(f"Error adding text to image: {err}", exc_info=True)

    async def _capture_snapshot(self, snapshot_path: Path):
        """Capture a single snapshot from camera."""
        # Пробуем разные возможные URL для снимка
        snapshot_urls = [
            # Стандартные OpenIPC URL
            f"http://{self.host}:{self.port}/image.jpg",
            f"http://{self.host}:{self.port}/cgi-bin/api.cgi?cmd=Snap&channel=0",
            f"http://{self.host}:{self.port}/cgi-bin/snapshot.cgi",
            f"http://{self.host}:{self.port}/snapshot.jpg",
            f"http://{self.host}:{self.port}/img/snapshot.cgi",
            f"http://{self.host}:{self.port}/cgi-bin/currentpic.cgi",
            f"http://{self.host}:{self.port}/tmpfs/auto.jpg",
            f"http://{self.host}:{self.port}/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=wuuPhkmj&user={self.username}&password={self.password}",
        ]
        
        last_error = None
        for url in snapshot_urls:
            try:
                _LOGGER.debug(f"Trying snapshot URL: {url}")
                async with self.session.get(url, auth=self.auth, timeout=10) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '')
                        if 'image' in content_type or content_type.startswith('image/'):
                            data = await response.read()
                            if len(data) > 1000:  # Проверяем, что это не HTML страница с ошибкой
                                async with aiofiles.open(snapshot_path, 'wb') as f:
                                    await f.write(data)
                                _LOGGER.info(f"✅ Snapshot saved from {url}: {snapshot_path.name} ({len(data)} bytes)")
                                return True
                            else:
                                _LOGGER.warning(f"Snapshot too small ({len(data)} bytes) from {url}")
                        else:
                            _LOGGER.warning(f"Unexpected content type from {url}: {content_type}")
                    else:
                        _LOGGER.debug(f"URL {url} returned HTTP {response.status}")
            except Exception as err:
                last_error = err
                _LOGGER.debug(f"Error with URL {url}: {err}")
                continue
        
        # Если ничего не сработало, пробуем через координатор получить URL из конфига
        try:
            # Пробуем получить информацию о камере из координатора
            if self.hass.data.get(DOMAIN):
                for entry_id, coordinator in self.hass.data[DOMAIN].items():
                    if entry_id != "config" and hasattr(coordinator, 'host'):
                        # Пробуем прямой доступ к JPG через основной URL
                        url = f"http://{coordinator.host}:{coordinator.port}/image.jpg"
                        _LOGGER.debug(f"Trying coordinator URL: {url}")
                        async with self.session.get(url, auth=self.auth, timeout=10) as response:
                            if response.status == 200:
                                data = await response.read()
                                if len(data) > 1000:
                                    async with aiofiles.open(snapshot_path, 'wb') as f:
                                        await f.write(data)
                                    _LOGGER.info(f"✅ Snapshot saved from coordinator URL")
                                    return True
        except Exception as err:
            last_error = err
        
        _LOGGER.error(f"Failed to capture snapshot from any URL. Last error: {last_error}")
        raise Exception(f"Failed to capture snapshot: {last_error}")

    async def record_video(self, duration: int, snapshot_interval: int = 5, add_osd: bool = False, osd_config: dict = None) -> dict:
        """
        Record video by capturing snapshots and creating video.
        duration: длительность записи в секундах
        snapshot_interval: интервал между кадрами в секундах
        add_osd: добавлять ли OSD на видео
        osd_config: конфигурация OSD
        """
        temp_filename = self._generate_filename(duration)
        temp_filepath = self.record_folder / temp_filename
        
        _LOGGER.info("Starting recording to %s for %d seconds", temp_filepath, duration)
        
        try:
            # Создаем временную папку для снимков
            temp_dir_name = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_dir = self.record_folder / temp_dir_name
            await asyncio.to_thread(temp_dir.mkdir, exist_ok=True)
            
            # Делаем снимки с заданным интервалом
            frames = duration // snapshot_interval
            if frames < 1:
                frames = 1
                _LOGGER.warning(f"Duration too short, recording at least 1 frame")
            
            # Получаем данные для OSD, если нужно
            osd_values = None
            osd_lines = None
            if add_osd and osd_config:
                osd_values = await self._get_osd_values()
                template = osd_config.get('template', 'OSD TEST')
                try:
                    osd_text = template.format(**osd_values)
                    osd_lines = [line.strip() for line in osd_text.split('\n') if line.strip()]
                    _LOGGER.info(f"OSD text to add: {osd_text}")
                    _LOGGER.info(f"OSD lines: {osd_lines}")
                except Exception as e:
                    _LOGGER.error(f"Template error: {e}")
                    osd_lines = ["OSD TEST"]
            
            successful_frames = 0
            for i in range(frames):
                snapshot_path = temp_dir / f"frame_{i:04d}.jpg"
                try:
                    await self._capture_snapshot(snapshot_path)
                    successful_frames += 1
                    
                    # Если нужно добавить OSD, добавляем текст на снимок
                    if add_osd and osd_lines and PIL_AVAILABLE:
                        await self._add_text_to_image(snapshot_path, osd_lines, osd_config)
                        if i == 0:
                            _LOGGER.info(f"Added OSD to frame {i}")
                    
                except Exception as e:
                    _LOGGER.error(f"Failed to capture frame {i}: {e}")
                
                # Ждем следующий кадр, если это не последний
                if i < frames - 1:
                    await asyncio.sleep(snapshot_interval)
            
            if successful_frames == 0:
                raise Exception("No frames captured successfully")
            
            # Создаем видео из снимков
            await self._create_video_from_frames(temp_dir, temp_filepath, successful_frames)
            
            final_filepath = temp_filepath
            final_filename = temp_filename
            
            # Удаляем временные файлы
            await self._cleanup_temp_files_async(temp_dir)
            
            # Получаем информацию о файле
            file_size = await asyncio.to_thread(os.path.getsize, final_filepath) if await asyncio.to_thread(final_filepath.exists) else 0
            
            result = {
                "success": True,
                "filepath": str(final_filepath),
                "filename": final_filename,
                "size": file_size,
                "duration": duration,
                "frames": successful_frames,
                "camera": self.camera_name,
                "timestamp": datetime.now().isoformat(),
                "url": f"/media/local/openipc_recordings/{self.camera_name}/{final_filename}",
                "osd_added": add_osd
            }
            
            _LOGGER.info("Recording completed: %s (%d bytes, %d frames)", final_filename, file_size, successful_frames)
            return result
            
        except Exception as err:
            _LOGGER.error("Recording failed: %s", err)
            if 'temp_dir' in locals():
                await self._cleanup_temp_files_async(temp_dir)
            return {
                "success": False,
                "error": str(err)
            }

    async def _create_video_from_frames(self, temp_dir: Path, output_path: Path, frame_count: int, fps: int = 1):
        """Create video from frames using ffmpeg."""
        # Проверяем наличие ffmpeg
        import shutil
        if not shutil.which("ffmpeg"):
            _LOGGER.error("ffmpeg not found. Cannot create video.")
            raise Exception("ffmpeg not found")
        
        # Путь к первому кадру для определения параметров
        first_frame = temp_dir / "frame_0000.jpg"
        if not await asyncio.to_thread(first_frame.exists):
            _LOGGER.error("No frames found to create video")
            raise Exception("No frames available")
        
        # Создаем видео с помощью ffmpeg
        cmd = [
            "ffmpeg",
            "-y",  # Перезаписывать выходной файл
            "-framerate", str(fps),  # Частота кадров
            "-pattern_type", "glob",
            "-i", str(temp_dir / "frame_*.jpg"),  # Входные файлы
            "-c:v", "libx264",  # Кодек H.264
            "-pix_fmt", "yuv420p",  # Формат пикселей для совместимости
            "-preset", "medium",  # Пресет кодирования
            "-crf", "23",  # Качество (меньше = лучше)
            str(output_path)
        ]
        
        _LOGGER.debug(f"Running ffmpeg: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                _LOGGER.error(f"FFmpeg error: {error_msg}")
                raise Exception(f"FFmpeg failed: {error_msg}")
            
            _LOGGER.info(f"Video created successfully: {output_path}")
            
        except Exception as err:
            _LOGGER.error(f"Error creating video: {err}")
            raise

    async def _cleanup_temp_files_async(self, temp_dir: Path):
        """Clean up temporary files."""
        try:
            if await asyncio.to_thread(temp_dir.exists):
                # Удаляем все файлы во временной папке
                for file in await asyncio.to_thread(lambda: list(temp_dir.glob("*"))):
                    await asyncio.to_thread(os.remove, file)
                # Удаляем саму папку
                await asyncio.to_thread(temp_dir.rmdir)
                _LOGGER.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as err:
            _LOGGER.error(f"Error cleaning up temp files: {err}")

    async def _check_rtsp_available(self, rtsp_url: str) -> bool:
        """Check if RTSP stream is available."""
        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-t", "1",
            "-f", "null",
            "-"
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            return process.returncode == 0
        except:
            return False

    async def record_rtsp_stream(self, duration: int, stream_profile: str = "main", with_audio: bool = False) -> dict:
        """
        Record video directly from RTSP stream (requires ffmpeg).
        """
        filename = self._generate_filename(duration)
        filepath = self.record_folder / filename
        
        # Проверяем разные возможные RTSP пути
        rtsp_paths = [
            "/stream=0",
            "/av0_0",
            "/live",
            "/h264",
            "/video",
            "/ch0",
            "/cam/realmonitor?channel=1&subtype=0",
        ]
        
        if stream_profile == "main":
            stream_path = "/stream=0"
        else:
            stream_path = "/stream=1"
        
        rtsp_url = f"rtsp://{self.username}:{self.password}@{self.host}:554{stream_path}"
        
        _LOGGER.info("Starting RTSP recording to %s for %d seconds (URL: %s)", 
                    filepath, duration, rtsp_url)
        
        # Сначала проверяем доступность RTSP
        if not await self._check_rtsp_available(rtsp_url):
            _LOGGER.error("RTSP stream not available at %s", rtsp_url)
            # Пробуем альтернативные пути
            for alt_path in rtsp_paths:
                if alt_path == stream_path:
                    continue
                alt_url = f"rtsp://{self.username}:{self.password}@{self.host}:554{alt_path}"
                _LOGGER.info("Trying alternative RTSP URL: %s", alt_url)
                if await self._check_rtsp_available(alt_url):
                    rtsp_url = alt_url
                    stream_path = alt_path
                    _LOGGER.info("Found working RTSP URL: %s", alt_url)
                    break
            else:
                return {
                    "success": False,
                    "error": "No working RTSP URL found"
                }
        
        # Базовые параметры ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-t", str(duration),
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
        ]
        
        if with_audio:
            cmd.extend([
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
            ])
        else:
            cmd.extend([
                "-an",
                "-c:v", "copy",
            ])
        
        cmd.extend([
            "-f", "mp4",
            str(filepath)
        ])
        
        _LOGGER.debug("FFmpeg command: %s", " ".join(cmd))
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                file_size = await asyncio.to_thread(os.path.getsize, filepath) if await asyncio.to_thread(filepath.exists) else 0
                result = {
                    "success": True,
                    "filepath": str(filepath),
                    "filename": filename,
                    "size": file_size,
                    "duration": duration,
                    "camera": self.camera_name,
                    "timestamp": datetime.now().isoformat(),
                    "url": f"/media/local/openipc_recordings/{self.camera_name}/{filename}",
                    "method": "rtsp",
                    "audio": with_audio,
                    "rtsp_url": rtsp_url
                }
                _LOGGER.info("RTSP recording completed: %s", filename)
                return result
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                _LOGGER.error("FFmpeg error: %s", error_msg)
                
                if with_audio and "codec not currently supported" in error_msg:
                    _LOGGER.info("Retrying without audio...")
                    return await self.record_rtsp_stream(duration, stream_profile, False)
                
                if "Connection refused" in error_msg or "Connection timed out" in error_msg:
                    _LOGGER.info("Retrying with UDP transport...")
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-t", str(duration),
                        "-rtsp_transport", "udp",
                        "-i", rtsp_url,
                        "-an",
                        "-c:v", "copy",
                        "-f", "mp4",
                        str(filepath)
                    ]
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode == 0:
                        file_size = await asyncio.to_thread(os.path.getsize, filepath) if await asyncio.to_thread(filepath.exists) else 0
                        return {
                            "success": True,
                            "filepath": str(filepath),
                            "filename": filename,
                            "size": file_size,
                            "duration": duration,
                            "camera": self.camera_name,
                            "timestamp": datetime.now().isoformat(),
                            "url": f"/media/local/openipc_recordings/{self.camera_name}/{filename}",
                            "method": "rtsp_udp"
                        }
                
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as err:
            _LOGGER.error("RTSP recording failed: %s", err)
            return {
                "success": False,
                "error": str(err)
            }

    async def send_to_telegram_direct(self, filepath: Path, bot_token: str, chat_id: str, caption: str = None, max_retries: int = 5) -> bool:
        """
        Send file directly to Telegram API с повторными попытками и динамическим таймаутом.
        """
        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        
        # Проверяем размер файла
        file_size_mb = (await asyncio.to_thread(os.path.getsize, filepath)) / 1024 / 1024
        if file_size_mb > 50:
            _LOGGER.error("File too large for Telegram: %.2f MB (max 50 MB)", file_size_mb)
            return False
        
        # Динамический таймаут
        timeout_seconds = max(120, min(600, int(file_size_mb * 30)))
        
        _LOGGER.info("=" * 50)
        _LOGGER.info("Sending video directly to Telegram API")
        _LOGGER.info("File: %s", filepath.name)
        _LOGGER.info("Size: %.2f MB", file_size_mb)
        _LOGGER.info("Timeout: %d seconds", timeout_seconds)
        _LOGGER.info("Max retries: %d", max_retries)
        _LOGGER.info("=" * 50)
        
        for attempt in range(max_retries):
            try:
                _LOGGER.info("📤 Attempt %d/%d - Starting upload...", attempt + 1, max_retries)
                
                current_timeout = timeout_seconds * (attempt + 1)
                
                timeout = aiohttp.ClientTimeout(
                    total=current_timeout,
                    connect=60,
                    sock_read=current_timeout,
                    sock_connect=60
                )
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with aiofiles.open(filepath, 'rb') as f:
                        file_data = await f.read()
                    
                    data = aiohttp.FormData()
                    data.add_field('chat_id', str(chat_id))
                    data.add_field('video', file_data, filename=filepath.name, content_type='video/mp4')
                    
                    if caption:
                        full_caption = caption
                    else:
                        full_caption = f"📹 Запись с камеры {Path(filepath).parent.parent.name}"
                    
                    full_caption += f"\n⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    full_caption += f"\n📊 {file_size_mb:.1f} MB"
                    
                    if len(full_caption) > 1024:
                        full_caption = full_caption[:1020] + "..."
                    
                    data.add_field('caption', full_caption)
                    
                    start_time = time.time()
                    
                    async with session.post(url, data=data) as response:
                        elapsed = time.time() - start_time
                        result = await response.json()
                        
                        if result.get('ok'):
                            _LOGGER.info("✅✅✅ SUCCESS (attempt %d) - Time: %.1f sec", attempt + 1, elapsed)
                            return True
                        else:
                            error_desc = result.get('description', 'Unknown error')
                            _LOGGER.warning("❌ Attempt %d failed after %.1f sec: %s", 
                                          attempt + 1, elapsed, error_desc)
                            
                            if "file is too big" in error_desc.lower():
                                _LOGGER.error("File too large for Telegram: %s", error_desc)
                                return False
                            
                            if attempt < max_retries - 1:
                                wait_time = 10 * (attempt + 1)
                                _LOGGER.info("Waiting %d seconds before retry...", wait_time)
                                await asyncio.sleep(wait_time)
                            
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time if 'start_time' in locals() else 0
                _LOGGER.warning("⏱ TIMEOUT (attempt %d) after %.1f sec", attempt + 1, elapsed)
                if attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    await asyncio.sleep(wait_time)
                    
            except Exception as err:
                _LOGGER.error("💥 Error (attempt %d): %s", attempt + 1, err)
                if attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    await asyncio.sleep(wait_time)
        
        _LOGGER.error("❌❌❌ All %d attempts failed", max_retries)
        return False

    async def send_to_telegram_via_service(self, filepath: Path, caption: str = None, chat_id: str = None) -> bool:
        """Send video using telegram_bot.send_video service."""
        if not await asyncio.to_thread(filepath.exists):
            _LOGGER.error("File %s not found", filepath)
            return False
        
        file_size_mb = (await asyncio.to_thread(os.path.getsize, filepath)) / 1024 / 1024
        _LOGGER.info("Sending video via telegram_bot service: %s (%.2f MB)", filepath.name, file_size_mb)
        
        if file_size_mb > 50:
            _LOGGER.error("File too large for Telegram: %.2f MB (max 50 MB)", file_size_mb)
            return False
        
        timeout_seconds = max(120, min(600, int(file_size_mb * 30)))
        
        try:
            if caption:
                full_caption = caption
            else:
                full_caption = f"📹 Запись с камеры {Path(filepath).parent.parent.name}"
            
            full_caption += f"\n⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            full_caption += f"\n📊 {file_size_mb:.1f} MB"
            
            service_data = {
                "file": str(filepath),
                "caption": full_caption,
                "disable_notification": False
            }
            
            if chat_id:
                service_data["target"] = chat_id
            
            await asyncio.wait_for(
                self.hass.services.async_call(
                    "telegram_bot",
                    "send_video",
                    service_data,
                    blocking=True
                ),
                timeout=timeout_seconds
            )
            
            _LOGGER.info("✅ Video sent via telegram_bot service: %s", filepath.name)
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.error("⏱ Timeout after %d seconds", timeout_seconds)
            return False
        except Exception as err:
            _LOGGER.error("❌ Failed: %s", err)
            return False

    async def send_to_telegram(self, filepath: Path, caption: str = None, chat_id: str = None) -> bool:
        """Send recorded video to Telegram."""
        if not await asyncio.to_thread(filepath.exists):
            _LOGGER.error("File %s not found", filepath)
            return False
        
        file_size = await asyncio.to_thread(os.path.getsize, filepath)
        file_size_mb = file_size / 1024 / 1024
        _LOGGER.info("=" * 60)
        _LOGGER.info("📤 ATTEMPTING TO SEND FILE TO TELEGRAM")
        _LOGGER.info("File: %s", filepath.name)
        _LOGGER.info("Size: %.2f MB", file_size_mb)
        _LOGGER.info("Path: %s", filepath)
        _LOGGER.info("=" * 60)
        
        if file_size_mb > 50:
            _LOGGER.error("❌ File too large for Telegram: %.2f MB (max 50 MB)", file_size_mb)
            return False
        
        telegram_config = self._get_telegram_config()
        bot_token = telegram_config["bot_token"]
        default_chat_id = telegram_config["chat_id"]
        
        target_chat_id = chat_id or default_chat_id
        
        _LOGGER.debug("Telegram config: bot_token=%s, chat_id=%s", 
                     "✅" if bot_token else "❌", target_chat_id or "❌")
        
        if not target_chat_id:
            _LOGGER.error("❌ No chat_id provided")
            return False
        
        has_send_video = self.hass.services.has_service("telegram_bot", "send_video")
        has_send_file = self.hass.services.has_service("telegram_bot", "send_file")
        has_notify = self.hass.services.has_service("notify", "telegram_notify")
        
        _LOGGER.debug("Available services: send_video=%s, send_file=%s, notify=%s", 
                     has_send_video, has_send_file, has_notify)
        
        # Method 1: Direct API
        if bot_token and target_chat_id:
            _LOGGER.info("📡 Method 1: Direct Telegram API")
            try:
                success = await self.send_to_telegram_direct(filepath, bot_token, target_chat_id, caption, max_retries=3)
                if success:
                    _LOGGER.info("✅✅✅ Method 1 successful")
                    return True
            except Exception as err:
                _LOGGER.error("Method 1 exception: %s", err)
        
        # Method 2: send_video service
        if has_send_video:
            _LOGGER.info("📡 Method 2: telegram_bot.send_video")
            try:
                success = await self.send_to_telegram_via_service(filepath, caption, target_chat_id)
                if success:
                    _LOGGER.info("✅✅✅ Method 2 successful")
                    return True
            except Exception as err:
                _LOGGER.error("Method 2 exception: %s", err)
        
        # Method 3: send_file service
        if has_send_file:
            _LOGGER.info("📡 Method 3: telegram_bot.send_file")
            try:
                service_data = {
                    "file": str(filepath),
                    "caption": caption or f"📹 Запись с камеры\n⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n📊 {file_size_mb:.1f} MB"
                }
                if target_chat_id:
                    service_data["target"] = target_chat_id
                
                await asyncio.wait_for(
                    self.hass.services.async_call(
                        "telegram_bot",
                        "send_file",
                        service_data,
                        blocking=True
                    ),
                    timeout=120
                )
                _LOGGER.info("✅✅✅ Method 3 successful")
                return True
            except Exception as err:
                _LOGGER.warning("Method 3 failed: %s", err)
        
        # Method 4: notify
        if has_notify:
            _LOGGER.info("📡 Method 4: notify.telegram_notify")
            try:
                message = caption or f"📹 Запись с камеры"
                message += f"\n⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                message += f"\n📊 {file_size_mb:.1f} MB"
                
                service_data = {
                    "message": message,
                    "data": {
                        "file": str(filepath)
                    }
                }
                if target_chat_id:
                    service_data["target"] = target_chat_id
                
                await asyncio.wait_for(
                    self.hass.services.async_call(
                        "notify",
                        "telegram_notify",
                        service_data,
                        blocking=True
                    ),
                    timeout=120
                )
                _LOGGER.info("✅✅✅ Method 4 successful")
                return True
            except Exception as err:
                _LOGGER.warning("Method 4 failed: %s", err)
        
        _LOGGER.error("❌❌❌ ALL METHODS FAILED")
        return False

    async def test_telegram_file_send(self, chat_id: str = None) -> dict:
        """Test sending a file to Telegram."""
        results = {
            "methods_tested": [],
            "results": {},
            "success": False,
            "diagnostics": {}
        }
        
        _LOGGER.info("=" * 50)
        _LOGGER.info("Starting Telegram file send test")
        
        telegram_config = self._get_telegram_config()
        bot_token = telegram_config["bot_token"]
        default_chat_id = telegram_config["chat_id"]
        target_chat_id = chat_id or default_chat_id
        
        results["diagnostics"]["has_bot_token"] = bool(bot_token)
        results["diagnostics"]["has_chat_id"] = bool(target_chat_id)
        results["diagnostics"]["config_source"] = "YAML (openipc section)"
        
        results["diagnostics"]["available_services"] = []
        for domain in self.hass.services.async_services():
            for service in self.hass.services.async_services()[domain]:
                if "telegram" in domain or "telegram" in service:
                    results["diagnostics"]["available_services"].append(f"{domain}.{service}")
        
        _LOGGER.debug("Available Telegram services: %s", results["diagnostics"]["available_services"])
        
        results["diagnostics"]["external_url"] = self.hass.config.external_url
        results["diagnostics"]["internal_url"] = self.hass.config.internal_url
        
        if not await asyncio.to_thread(self.record_folder.exists):
            _LOGGER.warning("Record folder does not exist, creating it")
            await self._ensure_folder_exists_async()
        
        test_file = self.record_folder / f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        try:
            async with aiofiles.open(test_file, 'w') as f:
                await f.write(f"Test file from Home Assistant\n")
                await f.write(f"Camera: {self.camera_name}\n")
                await f.write(f"Timestamp: {datetime.now()}\n")
                await f.write("This is a test file to verify Telegram file sending.")
            
            _LOGGER.info("Test file created: %s", test_file)
            _LOGGER.info("File size: %d bytes", await asyncio.to_thread(os.path.getsize, test_file))
            
            if bot_token and target_chat_id:
                results["methods_tested"].append("direct_api (YAML)")
                try:
                    success = await self.send_to_telegram_direct(test_file, bot_token, target_chat_id, "📱 Direct API Test", max_retries=2)
                    results["results"]["direct_api (YAML)"] = "✅ Success" if success else "❌ Failed"
                except Exception as err:
                    results["results"]["direct_api (YAML)"] = f"❌ Failed: {str(err)[:100]}"
            
            if self.hass.services.has_service("telegram_bot", "send_video"):
                results["methods_tested"].append("telegram_bot.send_video (UI)")
                try:
                    success = await self.send_to_telegram_via_service(test_file, "📱 Video Test", target_chat_id)
                    results["results"]["telegram_bot.send_video (UI)"] = "✅ Success" if success else "❌ Failed"
                except Exception as err:
                    results["results"]["telegram_bot.send_video (UI)"] = f"❌ Failed: {str(err)[:100]}"
            
            if self.hass.services.has_service("telegram_bot", "send_file"):
                results["methods_tested"].append("telegram_bot.send_file (UI)")
                try:
                    service_data = {
                        "file": str(test_file),
                        "caption": f"📱 Test: send_file from {self.camera_name}"
                    }
                    if target_chat_id:
                        service_data["target"] = target_chat_id
                    
                    await asyncio.wait_for(
                        self.hass.services.async_call(
                            "telegram_bot",
                            "send_file",
                            service_data,
                            blocking=True
                        ),
                        timeout=30
                    )
                    results["results"]["telegram_bot.send_file (UI)"] = "✅ Success"
                except Exception as err:
                    results["results"]["telegram_bot.send_file (UI)"] = f"❌ Failed: {str(err)[:100]}"
            
            if self.hass.services.has_service("notify", "telegram_notify"):
                results["methods_tested"].append("notify.telegram_notify")
                try:
                    service_data = {
                        "message": f"📱 Test: notify from {self.camera_name}",
                        "data": {
                            "file": str(test_file)
                        }
                    }
                    if target_chat_id:
                        service_data["target"] = target_chat_id
                    
                    await asyncio.wait_for(
                        self.hass.services.async_call(
                            "notify",
                            "telegram_notify",
                            service_data,
                            blocking=True
                        ),
                        timeout=30
                    )
                    results["results"]["notify.telegram_notify"] = "✅ Success"
                except Exception as err:
                    results["results"]["notify.telegram_notify"] = f"❌ Failed: {str(err)[:100]}"
            
            results["success"] = any("✅" in str(result) for result in results["results"].values())
            
            message = f"📱 **Telegram Test Results for {self.camera_name}**\n\n"
            message += f"**Bot Token (YAML):** {'✅ Configured' if bot_token else '❌ Not configured'}\n"
            message += f"**Chat ID (YAML):** {'✅ Configured' if default_chat_id else '❌ Not configured'}\n"
            message += f"**Target Chat ID:** {target_chat_id or 'Not set'}\n"
            message += f"**External URL:** {self.hass.config.external_url or 'Not set'}\n\n"
            message += "**Available services:**\n"
            for service in results["diagnostics"]["available_services"][:10]:
                message += f"• {service}\n"
            message += "\n**Test results:**\n"
            for method, result in results["results"].items():
                message += f"• {method}: {result}\n"
            
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Telegram Test Results",
                    "message": message,
                    "notification_id": f"openipc_telegram_test_{int(time.time())}"
                },
                blocking=True
            )
            
        except Exception as err:
            _LOGGER.error("Error during test: %s", err)
            results["error"] = str(err)
        
        finally:
            if test_file.exists():
                try:
                    await asyncio.to_thread(test_file.unlink)
                    _LOGGER.debug("Test file deleted")
                except Exception as err:
                    _LOGGER.warning("Failed to delete test file: %s", err)
        
        return results

    async def record_and_send_to_telegram(self, duration: int, method: str = "snapshots", 
                                         caption: str = None, chat_id: str = None) -> dict:
        """Record video and send to Telegram."""
        if method == "rtsp":
            result = await self.record_rtsp_stream(duration, "main", False)
        else:
            result = await self.record_video(duration)
        
        if result.get("success"):
            filepath = Path(result["filepath"])
            telegram_success = await self.send_to_telegram(filepath, caption, chat_id)
            result["telegram_sent"] = telegram_success
            
            if telegram_success:
                _LOGGER.info("Video recorded and sent to Telegram: %s", result["filename"])
            else:
                _LOGGER.warning("Video recorded but failed to send to Telegram: %s", result["filename"])
        
        return result

    async def get_recordings_list(self, limit: int = 20) -> list:
        """Get list of recordings in the folder."""
        recordings = []
        try:
            if not await asyncio.to_thread(self.record_folder.exists):
                return []
            
            files = await asyncio.to_thread(lambda: list(self.record_folder.glob("*.mp4")))
            sorted_files = sorted(files, key=lambda x: x.stat().st_ctime, reverse=True)[:limit]
            
            for file in sorted_files:
                stat = await asyncio.to_thread(file.stat)
                recordings.append({
                    "filename": file.name,
                    "path": str(file),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "url": f"/media/local/openipc_recordings/{self.camera_name}/{file.name}"
                })
        except Exception as err:
            _LOGGER.error("Error getting recordings list: %s", err)
        
        return recordings

    async def delete_recording(self, filename: str) -> bool:
        """Delete a recording file."""
        filepath = self.record_folder / filename
        try:
            if await asyncio.to_thread(filepath.exists):
                await asyncio.to_thread(filepath.unlink)
                _LOGGER.info("Deleted recording: %s", filename)
                return True
        except Exception as err:
            _LOGGER.error("Failed to delete %s: %s", filename, err)
        return False

    async def diagnose_rtsp(self) -> dict:
        """Diagnose RTSP stream."""
        results = {}
        rtsp_paths = [
            "/stream=0",
            "/stream=1", 
            "/av0_0",
            "/av0_1",
            "/live",
            "/live0",
            "/live1",
            "/h264",
            "/h265",
            "/video",
            "/video0",
            "/video1",
            "/ch0",
            "/ch1",
            "/cam/realmonitor?channel=1&subtype=0",
            "/cam/realmonitor?channel=1&subtype=1",
            "/media/video1",
            "/media/video2",
            "/mjpeg/1",
            "/mjpeg/2",
            "/bytestream",
            "/",
        ]
        
        for path in rtsp_paths:
            url = f"rtsp://{self.username}:{self.password}@{self.host}:554{path}"
            try:
                _LOGGER.debug("Testing RTSP URL: %s", url)
                cmd = [
                    "ffmpeg",
                    "-rtsp_transport", "tcp",
                    "-i", url,
                    "-t", "1",
                    "-f", "null",
                    "-"
                ]
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await process.communicate()
                success = process.returncode == 0
                results[path] = {
                    "success": success,
                    "error": stderr.decode()[:200] if not success else None,
                    "url": url
                }
                if success:
                    _LOGGER.info("Found working RTSP path: %s", path)
            except Exception as err:
                results[path] = {
                    "success": False,
                    "error": str(err),
                    "url": url
                }
        
        return results

    async def diagnose_telegram(self) -> dict:
        """Diagnose Telegram bot configuration."""
        telegram_config = self._get_telegram_config()
        
        results = {
            "telegram_bot_service": self.hass.services.has_service("telegram_bot", "send_file"),
            "notify_service": self.hass.services.has_service("notify", "telegram_notify"),
            "available_services": [],
            "bot_token_configured": bool(telegram_config["bot_token"]),
            "chat_id_configured": bool(telegram_config["chat_id"])
        }
        
        services_to_check = ["send_document", "send_file", "send_video", "send_message", "send_photo"]
        for service in services_to_check:
            if self.hass.services.has_service("telegram_bot", service):
                results["available_services"].append(f"telegram_bot.{service}")
        
        results["external_url"] = self.hass.config.external_url
        results["internal_url"] = self.hass.config.internal_url
        
        if "telegram_bot.send_message" in results["available_services"]:
            try:
                await self.hass.services.async_call(
                    "telegram_bot",
                    "send_message",
                    {
                        "message": f"🔄 Тестовое сообщение от камеры {self.camera_name}"
                    },
                    blocking=True
                )
                results["test_message"] = "success"
            except Exception as err:
                results["test_message"] = f"failed: {err}"
        
        return results

    async def get_video_stream_url(self, filename: str) -> str:
        """Get streaming URL for a video file."""
        return f"/media/local/openipc_recordings/{self.camera_name}/{filename}"

    async def get_video_thumbnail(self, filename: str) -> bytes:
        """Get video thumbnail using ffmpeg."""
        filepath = self.record_folder / filename
        if not await asyncio.to_thread(filepath.exists):
            return None
        
        thumb_path = self.record_folder / f"thumb_{filename}.jpg"
        
        try:
            cmd = [
                "ffmpeg",
                "-i", str(filepath),
                "-ss", "00:00:01",
                "-vframes", "1",
                "-vf", "scale=320:-1",
                "-f", "image2",
                str(thumb_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if await asyncio.to_thread(thumb_path.exists):
                async with aiofiles.open(thumb_path, 'rb') as f:
                    thumb_data = await f.read()
                await asyncio.to_thread(thumb_path.unlink)
                return thumb_data
            
        except Exception as err:
            _LOGGER.error("Error creating thumbnail: %s", err)
        
        return None

    async def delete_all_recordings(self) -> bool:
        """Delete all recordings."""
        try:
            files = await asyncio.to_thread(lambda: list(self.record_folder.glob("*.mp4")))
            for file in files:
                await asyncio.to_thread(file.unlink)
            _LOGGER.info("Deleted all recordings (%d files)", len(files))
            return True
        except Exception as err:
            _LOGGER.error("Failed to delete all recordings: %s", err)
            return False

    async def get_recordings_stats(self) -> dict:
        """Get statistics about recordings."""
        stats = {
            "count": 0,
            "total_size_mb": 0,
            "oldest": None,
            "newest": None,
            "by_date": {}
        }
        
        try:
            files = await asyncio.to_thread(lambda: list(self.record_folder.glob("*.mp4")))
            
            for file in files:
                stat = await asyncio.to_thread(file.stat)
                size_mb = stat.st_size / 1024 / 1024
                created = datetime.fromtimestamp(stat.st_ctime)
                date_str = created.strftime("%Y-%m-%d")
                
                stats["count"] += 1
                stats["total_size_mb"] += size_mb
                
                if date_str not in stats["by_date"]:
                    stats["by_date"][date_str] = {
                        "count": 0,
                        "size_mb": 0
                    }
                stats["by_date"][date_str]["count"] += 1
                stats["by_date"][date_str]["size_mb"] += size_mb
                
                if stats["oldest"] is None or created < stats["oldest"]:
                    stats["oldest"] = created
                if stats["newest"] is None or created > stats["newest"]:
                    stats["newest"] = created
            
            if stats["oldest"]:
                stats["oldest"] = stats["oldest"].isoformat()
            if stats["newest"]:
                stats["newest"] = stats["newest"].isoformat()
            
        except Exception as err:
            _LOGGER.error("Error getting recordings stats: %s", err)
        
        return stats
"""Media player platform for OpenIPC (video playback)."""
import logging
import asyncio
from datetime import datetime
from pathlib import Path

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    BrowseMedia,
)
from homeassistant.components.media_player.const import (
    MediaType,
    RepeatMode,
)
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC media player for video playback."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Add media player for video playback
    media_player = OpenIPCVideoPlayer(coordinator, entry)
    async_add_entities([media_player])

class OpenIPCVideoPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of an OpenIPC video player."""

    def __init__(self, coordinator, entry):
        """Initialize the video player."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} Recordings"
        self._attr_unique_id = f"{entry.entry_id}_video_player"
        self._attr_icon = "mdi:video-box"
        
        # Поддерживаемые функции
        self._attr_supported_features = (
            MediaPlayerEntityFeature.BROWSE_MEDIA |
            MediaPlayerEntityFeature.PLAY_MEDIA |
            MediaPlayerEntityFeature.STOP |
            MediaPlayerEntityFeature.PAUSE |
            MediaPlayerEntityFeature.PREVIOUS_TRACK |
            MediaPlayerEntityFeature.NEXT_TRACK |
            MediaPlayerEntityFeature.SHUFFLE_SET |
            MediaPlayerEntityFeature.REPEAT_SET |
            MediaPlayerEntityFeature.SEEK |
            MediaPlayerEntityFeature.VOLUME_SET |
            MediaPlayerEntityFeature.VOLUME_MUTE
        )
        
        self._attr_state = MediaPlayerState.IDLE
        self._attr_volume_level = 0.5
        self._attr_is_volume_muted = False
        self._attr_shuffle = False
        self._attr_repeat = RepeatMode.OFF
        self._media_title = None
        self._media_artist = None
        self._media_album_name = None
        self._media_image_url = None
        self._media_content_id = None
        self._media_content_type = None
        self._media_duration = None
        self._media_position = None
        self._media_position_updated_at = None
        self._playlist = []
        self._playlist_index = 0
        self._current_filepath = None

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title

    @property
    def media_artist(self):
        """Return the artist of current playing media."""
        return self._media_artist

    @property
    def media_album_name(self):
        """Return the album name of current playing media."""
        return self._media_album_name

    @property
    def media_image_url(self):
        """Return the image URL of current playing media."""
        return None

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._media_content_id

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return self._media_content_type

    @property
    def media_duration(self):
        """Return the duration of current playing media."""
        return self._media_duration

    @property
    def media_position(self):
        """Return the position of current playing media."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """Return the time when the position was last updated."""
        return self._media_position_updated_at

    @property
    def shuffle(self):
        """Return if shuffling is enabled."""
        return self._attr_shuffle

    @property
    def repeat(self):
        """Return the repeat mode."""
        return self._attr_repeat

    @property
    def playlist(self):
        """Return the current playlist."""
        return self._playlist

    @property
    def playlist_index(self):
        """Return the index of the current playlist item."""
        return self._playlist_index

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Browse media."""
        try:
            _LOGGER.debug("Browsing media: type=%s, id=%s", media_content_type, media_content_id)
            
            # Если нет media_content_id, показываем корневую папку
            if media_content_id is None:
                return BrowseMedia(
                    title="OpenIPC Recordings",
                    media_class="directory",
                    media_content_type="videos",
                    media_content_id="recordings",
                    can_play=False,
                    can_expand=True,
                    children=[await self._browse_camera_folder()],
                )
            
            # Если запрошена папка камеры
            if media_content_id == "recordings":
                return await self._browse_camera_folder()
            
            # Если запрошена папка с записями камеры
            if media_content_id.startswith("camera:"):
                camera_name = media_content_id.replace("camera:", "")
                return await self._browse_recordings(camera_name)
            
        except Exception as err:
            _LOGGER.error("Error browsing media: %s", err, exc_info=True)
            return None
        
        return None

    async def _browse_camera_folder(self):
        """Browse camera folder."""
        try:
            camera_name = self.coordinator.recorder.camera_name
            
            children = [
                BrowseMedia(
                    title=f"{self.entry.data.get('name', 'OpenIPC Camera')} Recordings",
                    media_class="directory",
                    media_content_type="videos",
                    media_content_id=f"camera:{camera_name}",
                    can_play=False,
                    can_expand=True,
                )
            ]
            
            return BrowseMedia(
                title="OpenIPC Recordings",
                media_class="directory",
                media_content_type="videos",
                media_content_id="recordings",
                can_play=False,
                can_expand=True,
                children=children,
            )
            
        except Exception as err:
            _LOGGER.error("Error browsing camera folder: %s", err)
            return BrowseMedia(
                title="OpenIPC Recordings (Error)",
                media_class="directory",
                media_content_type="videos",
                media_content_id="recordings",
                can_play=False,
                can_expand=False,
                children=[],
            )

    async def _browse_recordings(self, camera_name):
        """Browse recordings for a specific camera."""
        try:
            # Получаем список записей
            recordings = await self.coordinator.recorder.get_recordings_list(limit=50)
            
            children = []
            for recording in recordings:
                # Формируем дату для отображения
                created = datetime.fromisoformat(recording['created'])
                size_mb = recording['size'] / 1024 / 1024
                title = f"{created.strftime('%Y-%m-%d %H:%M:%S')} ({size_mb:.1f} MB)"
                
                children.append(
                    BrowseMedia(
                        title=title,
                        media_class="video",
                        media_content_type="video/mp4",
                        media_content_id=f"file:{recording['filename']}",
                        can_play=True,
                        can_expand=False,
                        thumbnail=None,
                    )
                )
            
            return BrowseMedia(
                title=f"{camera_name} Recordings",
                media_class="directory",
                media_content_type="videos",
                media_content_id=f"camera:{camera_name}",
                can_play=False,
                can_expand=True,
                children=children,
            )
            
        except Exception as err:
            _LOGGER.error("Error browsing recordings: %s", err)
            return BrowseMedia(
                title=f"{camera_name} Recordings (Error)",
                media_class="directory",
                media_content_type="videos",
                media_content_id=f"camera:{camera_name}",
                can_play=False,
                can_expand=False,
                children=[],
            )

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.info("Play media called with type=%s, id=%s", media_type, media_id)
        
        if media_id.startswith("file:"):
            filename = media_id.replace("file:", "")
            filepath = self.coordinator.recorder.record_folder / filename
            
            if await asyncio.to_thread(filepath.exists):
                # Сохраняем путь к файлу
                self._current_filepath = filepath
                
                # Создаем URL для потоковой передачи через HA
                # Используем /api/media_player/media_source вместо прямого пути к файлу
                media_url = f"/api/media_player/media_source?media_content_id=media-source://media_source/local/openipc_recordings/{self.coordinator.recorder.camera_name}/{filename}"
                
                self._media_content_id = media_url
                self._media_content_type = "video"
                self._media_title = filename
                self._media_artist = self.entry.data.get('name', 'OpenIPC Camera')
                self._media_album_name = "Recordings"
                
                # Пытаемся получить длительность видео через ffmpeg
                duration = await self._get_video_duration(filepath)
                if duration:
                    self._media_duration = duration
                
                self._attr_state = MediaPlayerState.PLAYING
                self._media_position = 0
                self._media_position_updated_at = dt_util.utcnow()
                
                self.async_write_ha_state()
                _LOGGER.info("Playing video: %s with URL: %s", filename, media_url)
            else:
                _LOGGER.error("File not found: %s", filepath)

    async def _get_video_duration(self, filepath):
        """Get video duration using ffmpeg."""
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(filepath)
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            import json
            data = json.loads(stdout)
            if 'format' in data and 'duration' in data['format']:
                return float(data['format']['duration'])
        except Exception as err:
            _LOGGER.debug("Could not get video duration: %s", err)
        return None

    async def async_media_play(self):
        """Send play command."""
        self._attr_state = MediaPlayerState.PLAYING
        self._media_position_updated_at = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_media_pause(self):
        """Send pause command."""
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self):
        """Send stop command."""
        self._attr_state = MediaPlayerState.IDLE
        self._media_content_id = None
        self._media_title = None
        self._media_position = None
        self._media_position_updated_at = None
        self._current_filepath = None
        self.async_write_ha_state()

    async def async_media_previous_track(self):
        """Send previous track command."""
        if self._playlist and self._playlist_index > 0:
            self._playlist_index -= 1
            await self.async_play_media("video", self._playlist[self._playlist_index])

    async def async_media_next_track(self):
        """Send next track command."""
        if self._playlist and self._playlist_index < len(self._playlist) - 1:
            self._playlist_index += 1
            await self.async_play_media("video", self._playlist[self._playlist_index])

    async def async_media_seek(self, position):
        """Send seek command."""
        self._media_position = position
        self._media_position_updated_at = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume):
        """Set volume level."""
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        """Mute the volume."""
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_set_shuffle(self, shuffle):
        """Set shuffle mode."""
        self._attr_shuffle = shuffle
        self.async_write_ha_state()

    async def async_set_repeat(self, repeat):
        """Set repeat mode."""
        self._attr_repeat = repeat
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {})
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "OpenIPC Camera"),
            "manufacturer": "OpenIPC",
            "model": parsed.get("model", "Camera"),
            "sw_version": parsed.get("firmware", "Unknown"),
        }
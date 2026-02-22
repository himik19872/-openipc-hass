"""Media source for OpenIPC recordings."""
from __future__ import annotations

import os
import asyncio
from datetime import datetime
from pathlib import Path

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_get_media_source(hass: HomeAssistant) -> OpenIPCMediaSource:
    """Set up OpenIPC media source."""
    return OpenIPCMediaSource(hass)

class OpenIPCMediaSource(MediaSource):
    """Provide OpenIPC recordings as media sources."""

    name: str = "OpenIPC Recordings"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize OpenIPCMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        # Извлекаем путь из идентификатора
        path = item.identifier
        media_path = Path(self.hass.config.path("media")) / path
        
        # Проверяем существование файла асинхронно
        exists = await asyncio.to_thread(media_path.exists)
        if not exists:
            raise ValueError(f"Media not found: {path}")
        
        url = f"/media/local/{path}"
        return PlayMedia(url, "video/mp4")

    async def async_browse_media(
        self, item: MediaSourceItem
    ) -> BrowseMediaSource:
        """Browse media."""
        # Корневая папка
        if not item.identifier:
            return self._build_root()
        
        # Разбираем путь
        parts = item.identifier.split("/")
        
        # Если запрошена корневая папка openipc_recordings
        if len(parts) == 1 and parts[0] == "openipc_recordings":
            return await self._browse_recordings_root()
        
        # Если запрошена папка конкретной камеры
        if len(parts) == 2 and parts[0] == "openipc_recordings":
            camera_name = parts[1]
            return await self._browse_camera_recordings(camera_name)
        
        raise ValueError(f"Invalid identifier: {item.identifier}")

    def _build_root(self) -> BrowseMediaSource:
        """Build root media source."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class="directory",
            media_content_type="video",
            title="OpenIPC Recordings",
            can_play=False,
            can_expand=True,
            children_media_class="directory",
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="openipc_recordings",
                    media_class="directory",
                    media_content_type="video",
                    title="All Cameras",
                    can_play=False,
                    can_expand=True,
                )
            ],
        )

    async def _browse_recordings_root(self) -> BrowseMediaSource:
        """Browse root recordings folder - shows all cameras."""
        media_path = Path(self.hass.config.path("media")) / "openipc_recordings"
        
        children = []
        
        # Проверяем существование папки асинхронно
        exists = await asyncio.to_thread(media_path.exists)
        if exists:
            # Получаем список папок камер асинхронно
            camera_dirs = await asyncio.to_thread(
                lambda: [p for p in media_path.iterdir() if p.is_dir()]
            )
            
            # Сортируем папки по имени
            camera_dirs.sort(key=lambda p: p.name)
            
            for camera_path in camera_dirs:
                # Считаем количество видео в папке асинхронно
                video_files = await asyncio.to_thread(
                    lambda: list(camera_path.glob("*.mp4"))
                )
                video_count = len(video_files)
                
                # Получаем последнее видео для превью
                last_video = None
                if video_files:
                    last_video = max(video_files, key=lambda p: p.stat().st_ctime)
                
                title = f"{camera_path.name}"
                if video_count > 0:
                    title += f" ({video_count} videos)"
                
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"openipc_recordings/{camera_path.name}",
                        media_class="directory",
                        media_content_type="video",
                        title=title,
                        can_play=False,
                        can_expand=True,
                        thumbnail=None,
                    )
                )
        
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="openipc_recordings",
            media_class="directory",
            media_content_type="video",
            title="OpenIPC Cameras",
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class="directory",
        )

    async def _browse_camera_recordings(self, camera_name: str) -> BrowseMediaSource:
        """Browse recordings for a specific camera."""
        camera_path = Path(self.hass.config.path("media")) / "openipc_recordings" / camera_name
        
        children = []
        
        # Проверяем существование папки асинхронно
        exists = await asyncio.to_thread(camera_path.exists)
        if exists:
            # Получаем список видео файлов асинхронно (сортировка по дате, новые сверху)
            video_files = await asyncio.to_thread(
                lambda: sorted(
                    camera_path.glob("*.mp4"), 
                    key=lambda p: p.stat().st_ctime, 
                    reverse=True
                )
            )
            
            for video_file in video_files:
                # Получаем информацию о файле асинхронно
                stat = await asyncio.to_thread(video_file.stat)
                created = datetime.fromtimestamp(stat.st_ctime)
                size_mb = stat.st_size / 1024 / 1024
                
                # Парсим имя файла для получения длительности
                duration_text = ""
                if "_" in video_file.stem:
                    parts = video_file.stem.split("_")
                    if parts[-1].endswith("s"):
                        try:
                            duration = int(parts[-1][:-1])
                            duration_text = f" ({duration}s)"
                        except:
                            pass
                
                title = f"{created.strftime('%Y-%m-%d %H:%M:%S')}{duration_text} - {size_mb:.1f} MB"
                
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"openipc_recordings/{camera_name}/{video_file.name}",
                        media_class="video",
                        media_content_type="video/mp4",
                        title=title,
                        can_play=True,
                        can_expand=False,
                        thumbnail=None,
                    )
                )
        
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"openipc_recordings/{camera_name}",
            media_class="directory",
            media_content_type="video",
            title=f"{camera_name}",
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class="video",
        )
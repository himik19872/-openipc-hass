"""Media source for OpenIPC recordings."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.components.media_source import MediaSource, MediaSourceItem, PlayMedia, BrowseMediaSource

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
        return PlayMedia("", "")

    async def async_browse_media(
        self, item: MediaSourceItem
    ) -> BrowseMediaSource:
        """Browse media."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class="directory",
            media_content_type="",
            title="OpenIPC",
            can_play=False,
            can_expand=True,
        )
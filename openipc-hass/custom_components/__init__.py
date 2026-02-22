"""OpenIPC integration for Home Assistant."""
import asyncio
import logging
from datetime import timedelta, datetime
import re
import time
import voluptuous as vol
from pathlib import Path

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST, 
    CONF_PORT, 
    CONF_USERNAME, 
    CONF_PASSWORD,
    CONF_ENTITY_ID,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_component import EntityComponent

from .const import (
    DOMAIN,
    API_STATUS,
    DEFAULT_SCAN_INTERVAL,
    CONF_RTSP_PORT,
    MAJESTIC_CONFIG,
    METRICS_ENDPOINT,
    RECORD_START,
    RECORD_STOP,
    RECORD_STATUS,
    RECORD_MANUAL,
    DEFAULT_OSD_TEMPLATE,
    DEFAULT_OSD_POSITION,
    DEFAULT_OSD_FONT_SIZE,
    DEFAULT_OSD_COLOR,
    OSD_POSITIONS,
    OSD_COLORS,
)

from .recorder import OpenIPCRecorder

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera", "binary_sensor", "sensor", "switch", "button", "media_player", "select"]

# Schema for YAML configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("telegram_bot_token"): cv.string,
                vol.Optional("telegram_chat_id"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Service schemas
PLAY_AUDIO_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("media_id", default="beep"): cv.string,
})

TEST_AUDIO_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

SCAN_DEVICES_SCHEMA = vol.Schema({})

REBOOT_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

SET_IR_MODE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("mode"): vol.In(["0", "1", "2"]),
})

# Recording service schemas
START_RECORDING_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("duration"): vol.Coerce(int),
    vol.Optional("save_to_ha", default=True): cv.boolean,
    vol.Optional("method", default="snapshots"): vol.In(["snapshots", "rtsp"]),
})

STOP_RECORDING_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

TIMED_RECORDING_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("duration"): vol.Coerce(int),
    vol.Optional("save_to_ha", default=True): cv.boolean,
    vol.Optional("method", default="snapshots"): vol.In(["snapshots", "rtsp"]),
})

GET_RECORDINGS_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("limit", default=20): vol.Coerce(int),
})

DELETE_RECORDING_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("filename"): cv.string,
})

RECORD_AND_SEND_TELEGRAM_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("duration"): vol.Coerce(int),
    vol.Optional("method", default="snapshots"): vol.In(["snapshots", "rtsp"]),
    vol.Optional("caption"): cv.string,
    vol.Optional("chat_id"): cv.string,
})

# Diagnostic service schemas
DIAGNOSE_RTSP_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

DIAGNOSE_TELEGRAM_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

TEST_TELEGRAM_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("chat_id"): cv.string,
})

# Video playback service schemas
GET_RECORDINGS_STATS_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

DELETE_ALL_RECORDINGS_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

GET_VIDEO_THUMBNAIL_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("filename"): cv.string,
})

# OSD recording service schema
RECORD_WITH_OSD_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("duration"): vol.Coerce(int),
    vol.Optional("template", default=DEFAULT_OSD_TEMPLATE): cv.string,
    vol.Optional("position", default=DEFAULT_OSD_POSITION): vol.In(OSD_POSITIONS.keys()),
    vol.Optional("font_size", default=DEFAULT_OSD_FONT_SIZE): vol.Coerce(int),
    vol.Optional("color", default=DEFAULT_OSD_COLOR): vol.In(OSD_COLORS.keys()),
    vol.Optional("send_telegram", default=False): cv.boolean,
})

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the OpenIPC component."""
    hass.data.setdefault(DOMAIN, {})
    
    # Load configuration from configuration.yaml
    if DOMAIN in config:
        conf = config[DOMAIN]
        hass.data[DOMAIN]["config"] = conf
        _LOGGER.info("Loaded OpenIPC configuration: %s", conf)
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenIPC from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create coordinator for data updates
    coordinator = OpenIPCDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Register services
    await async_register_services(hass)
    
    # Set up all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Сервис для получения списка доступных шрифтов
    async def handle_list_fonts(call):
        """Handle the list_fonts service call."""
        if hasattr(coordinator, 'recorder') and coordinator.recorder:
            fonts = await coordinator.recorder.list_available_fonts()
            if fonts:
                message = f"📚 Найдено {len(fonts)} шрифтов:\n\n"
                for i, font in enumerate(fonts[:15], 1):
                    message += f"{i}. {font}\n"
                if len(fonts) > 15:
                    message += f"\n... и еще {len(fonts) - 15} шрифтов"
            else:
                message = "❌ Шрифты не найдены!\n\n"
                message += "Поместите .ttf файлы в папку:\n"
                message += "`/config/custom_components/openipc/openipc_fonts/`\n\n"
                message += "Шрифты можно скачать с:\n"
                message += "https://github.com/dejavu-fonts/dejavu-fonts"
            
            hass.components.persistent_notification.async_create(
                message,
                title="OpenIPC - Доступные шрифты",
                notification_id="openipc_fonts"
            )
        else:
            _LOGGER.error("Recorder not initialized")
    
    # Регистрируем сервис
    hass.services.async_register(DOMAIN, "list_fonts", handle_list_fonts)
    
    return True

async def async_register_services(hass: HomeAssistant) -> None:
    """Register services for OpenIPC."""
    
    async def async_find_coordinator_by_entity_id(entity_id):
        """Find coordinator by entity_id - использует ТОЛЬКО точное совпадение."""
        if not entity_id:
            _LOGGER.error("async_find_coordinator_by_entity_id called with empty entity_id")
            return None
            
        _LOGGER.debug("🔍 Looking for coordinator with entity_id: %s", entity_id)
        
        # Если entity_id пришел как список, берем первый элемент
        if isinstance(entity_id, list):
            if entity_id:
                entity_id = entity_id[0]
                _LOGGER.debug("Entity_id was list, using first element: %s", entity_id)
            else:
                _LOGGER.error("Entity_id is empty list")
                return None
        
        # Убеждаемся, что entity_id - строка
        if not isinstance(entity_id, str):
            _LOGGER.error("Entity_id is not a string: %s", type(entity_id))
            return None
        
        # Проходим по всем координаторам и ищем ТОЧНОЕ совпадение
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if entry_id == "config":  # Skip config entry
                continue
            
            if not hasattr(coordinator, 'recorder'):
                continue
            
            # Формируем точный entity_id для этой камеры
            camera_name = coordinator.recorder.camera_name
            camera_host = coordinator.host
            
            # Возможные точные варианты для этой камеры
            exact_ids = [
                f"camera.{camera_name}",                          # camera.openipc_camera
                f"camera.{camera_host.replace('.', '_')}",       # camera.192_168_1_106
                f"camera.{camera_host}",                          # camera.192.168.1.106
            ]
            
            _LOGGER.debug("Checking %s against exact IDs: %s", entity_id, exact_ids)
            
            # Только точное совпадение!
            if entity_id in exact_ids:
                _LOGGER.info("✅ Found exact match for %s (camera: %s, host: %s)", 
                            entity_id, camera_name, camera_host)
                return coordinator
        
        # Если точного совпадения нет - возвращаем None, а не первую камеру!
        _LOGGER.error("❌ No exact match found for entity_id: %s", entity_id)
        _LOGGER.error("   Please use one of these formats:")
        _LOGGER.error("   - camera.openipc_camera")
        _LOGGER.error("   - camera.%s (with underscores)", coordinator.host.replace('.', '_') if 'coordinator' in locals() else "192_168_1_xxx")
        _LOGGER.error("   - camera.%s (with dots)", coordinator.host if 'coordinator' in locals() else "192.168.1.xxx")
        return None
    
    async def async_find_media_player(entity_id: str):
        """Find media player entity by entity_id."""
        if not entity_id:
            return None
        component: EntityComponent = hass.data.get("entity_components", {}).get("media_player")
        if component:
            for entity in component.entities:
                if entity.entity_id == entity_id:
                    return entity
        return None
    
    async def async_find_button(entity_id: str):
        """Find button entity by entity_id."""
        if not entity_id:
            return None
        component: EntityComponent = hass.data.get("entity_components", {}).get("button")
        if component:
            for entity in component.entities:
                if entity.entity_id == entity_id:
                    return entity
        return None
    
    async def async_find_switch(entity_id: str):
        """Find switch entity by entity_id."""
        if not entity_id:
            return None
        component: EntityComponent = hass.data.get("entity_components", {}).get("switch")
        if component:
            for entity in component.entities:
                if entity.entity_id == entity_id:
                    return entity
        return None
    
    async def async_play_audio(call: ServiceCall) -> None:
        """Handle play audio service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        media_id = call.data.get("media_id", "beep")
        
        entity = await async_find_media_player(entity_id)
        if entity:
            await entity.async_play_media("audio", media_id)
            _LOGGER.debug("Play audio called on %s with media_id=%s", entity_id, media_id)
        else:
            _LOGGER.error("Media player entity %s not found", entity_id)
    
    async def async_test_audio(call: ServiceCall) -> None:
        """Handle test audio service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        entity = await async_find_media_player(entity_id)
        if entity:
            await entity.async_test_audio()
            _LOGGER.debug("Test audio called on %s", entity_id)
        else:
            _LOGGER.error("Media player entity %s not found", entity_id)
    
    async def async_reboot(call: ServiceCall) -> None:
        """Handle reboot service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        entity = await async_find_button(entity_id)
        if entity:
            await entity.async_press()
            _LOGGER.debug("Reboot called on %s", entity_id)
        else:
            _LOGGER.error("Button entity %s not found", entity_id)
    
    async def async_set_ir_mode(call: ServiceCall) -> None:
        """Handle set IR mode service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        mode = call.data["mode"]
        
        entity = await async_find_switch(entity_id)
        if entity:
            coordinator = await async_find_coordinator_by_entity_id(entity_id)
            if coordinator:
                if mode == "0":
                    await coordinator.async_set_night_mode("off")
                elif mode == "1":
                    await coordinator.async_set_night_mode("on")
                elif mode == "2":
                    await coordinator.async_set_night_mode("auto")
                _LOGGER.debug("Set IR mode %s on %s", mode, entity_id)
        else:
            _LOGGER.error("Switch entity %s not found", entity_id)
    
    async def async_scan_devices(call: ServiceCall) -> None:
        """Handle scan devices service."""
        try:
            from .discovery import OpenICPCDiscovery
            discovery = OpenICPCDiscovery(hass)
            devices = await discovery.discover_all()
            
            if devices:
                message = f"Found {len(devices)} OpenIPC camera(s):\n\n"
                for device in devices:
                    message += f"📍 **{device.get('name', 'OpenIPC Camera')}**\n"
                    message += f"   IP: {device['ip']}\n"
                    message += f"   Port: {device.get('port', 80)}\n"
                    message += f"   Source: {device.get('source', 'unknown')}\n"
                    if device.get('mac'):
                        message += f"   MAC: {device['mac']}\n"
                    if device.get('verified_by'):
                        message += f"   Verified: {device['verified_by']}\n"
                    message += "\n"
            else:
                message = "No OpenIPC cameras found on the network"
            
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "OpenIPC Discovery Results",
                    "message": message,
                    "notification_id": "openipc_discovery"
                },
                blocking=True
            )
        except Exception as err:
            _LOGGER.error("Scan devices error: %s", err)
    
    async def async_start_recording(call: ServiceCall) -> None:
        """Handle start recording service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        duration = call.data.get("duration")
        save_to_ha = call.data.get("save_to_ha", True)
        method = call.data.get("method", "snapshots")
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator:
            if duration:
                await coordinator.async_start_timed_recording(duration, save_to_ha, method)
            else:
                if save_to_ha:
                    _LOGGER.error("Duration required for HA media recording")
                else:
                    await coordinator.async_start_recording()
            _LOGGER.debug("Start recording called on %s", entity_id)
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    async def async_stop_recording(call: ServiceCall) -> None:
        """Handle stop recording service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator:
            await coordinator.async_stop_recording()
            _LOGGER.debug("Stop recording called on %s", entity_id)
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    async def async_timed_recording(call: ServiceCall) -> None:
        """Handle timed recording service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        duration = call.data["duration"]
        save_to_ha = call.data.get("save_to_ha", True)
        method = call.data.get("method", "snapshots")
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator:
            await coordinator.async_start_timed_recording(duration, save_to_ha, method)
            _LOGGER.debug("Timed recording called on %s for %d seconds", entity_id, duration)
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    async def async_get_recordings(call: ServiceCall) -> None:
        """Handle get recordings service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        limit = call.data.get("limit", 20)
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            recordings = await coordinator.recorder.get_recordings_list(limit)
            
            if recordings:
                message = f"📹 **Recordings for {coordinator.recorder.camera_name}**\n\n"
                for rec in recordings[:10]:
                    size_mb = rec['size'] / 1024 / 1024
                    message += f"• {rec['filename']}\n"
                    message += f"  📊 {size_mb:.1f} MB\n"
                    message += f"  📅 {rec['created']}\n\n"
            else:
                message = "No recordings found"
            
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"OpenIPC Recordings",
                    "message": message,
                    "notification_id": f"openipc_recordings_{coordinator.entry.entry_id}"
                },
                blocking=True
            )
        else:
            _LOGGER.error("Coordinator or recorder not found for entity %s", entity_id)

    async def async_delete_recording(call: ServiceCall) -> None:
        """Handle delete recording service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        filename = call.data["filename"]
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            success = await coordinator.recorder.delete_recording(filename)
            if success:
                _LOGGER.info("Deleted recording %s", filename)
            else:
                _LOGGER.error("Failed to delete recording %s", filename)
        else:
            _LOGGER.error("Coordinator or recorder not found for entity %s", entity_id)

    async def async_record_and_send_telegram(call: ServiceCall) -> None:
        """Handle record and send to Telegram service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        duration = call.data["duration"]
        method = call.data.get("method", "snapshots")
        caption = call.data.get("caption")
        chat_id = call.data.get("chat_id")
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            await coordinator.async_record_and_send_telegram(duration, method, caption, chat_id)
            _LOGGER.debug("Record and send Telegram called on %s", entity_id)
        else:
            _LOGGER.error("Coordinator or recorder not found for entity %s", entity_id)

    async def async_diagnose_rtsp(call: ServiceCall) -> None:
        """Handle diagnose RTSP service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            await coordinator.async_diagnose_rtsp()
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    async def async_diagnose_telegram(call: ServiceCall) -> None:
        """Handle diagnose Telegram service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            await coordinator.async_diagnose_telegram()
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    async def async_test_telegram(call: ServiceCall) -> None:
        """Handle test Telegram service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        chat_id = call.data.get("chat_id")
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            await coordinator.async_test_telegram(chat_id)
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    # Сервисы для просмотра видео
    async def async_get_recordings_stats(call: ServiceCall) -> None:
        """Handle get recordings statistics service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            stats = await coordinator.recorder.get_recordings_stats()
            
            message = f"📊 **Recordings Statistics for {coordinator.recorder.camera_name}**\n\n"
            message += f"**Total recordings:** {stats['count']}\n"
            message += f"**Total size:** {stats['total_size_mb']:.1f} MB\n"
            if stats['oldest']:
                message += f"**Oldest:** {stats['oldest']}\n"
            if stats['newest']:
                message += f"**Newest:** {stats['newest']}\n"
            
            if stats['by_date']:
                message += "\n**By date:**\n"
                for date, data in sorted(stats['by_date'].items()):
                    message += f"• {date}: {data['count']} files ({data['size_mb']:.1f} MB)\n"
            
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Recordings Statistics",
                    "message": message,
                    "notification_id": f"openipc_stats_{coordinator.entry.entry_id}"
                },
                blocking=True
            )
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    async def async_delete_all_recordings(call: ServiceCall) -> None:
        """Handle delete all recordings service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            success = await coordinator.recorder.delete_all_recordings()
            
            if success:
                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Recordings Deleted",
                        "message": f"✅ All recordings for {coordinator.recorder.camera_name} have been deleted.",
                        "notification_id": f"openipc_delete_{coordinator.entry.entry_id}"
                    },
                    blocking=True
                )
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    async def async_get_video_thumbnail(call: ServiceCall) -> None:
        """Handle get video thumbnail service."""
        entity_id = None
        if hasattr(call, 'target') and call.target:
            entity_id = call.target.get("entity_id")
        if not entity_id:
            entity_id = call.data.get(CONF_ENTITY_ID)
        
        filename = call.data["filename"]
        
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        if coordinator and hasattr(coordinator, 'recorder'):
            thumbnail = await coordinator.recorder.get_video_thumbnail(filename)
            if thumbnail:
                _LOGGER.info("Thumbnail created for %s", filename)
        else:
            _LOGGER.error("Coordinator not found for entity %s", entity_id)

    # Сервис для записи с OSD
    async def async_record_with_osd(call: ServiceCall) -> None:
        """Handle record with OSD service."""
        _LOGGER.debug("=" * 60)
        _LOGGER.debug("📹 RECORD WITH OSD CALLED")
        _LOGGER.debug("Call data: %s", call.data)
        _LOGGER.debug("Call target: %s", getattr(call, 'target', None))
        
        # ПОЛУЧАЕМ ENTITY_ID
        entity_id = None
        
        # Способ 1: Из target (новый стандарт HA)
        if hasattr(call, 'target') and call.target:
            target_entity = call.target.get("entity_id")
            if target_entity:
                entity_id = target_entity
                _LOGGER.debug("Got entity_id from target: %s", entity_id)
        
        # Способ 2: Из data (старый способ)
        if not entity_id:
            data_entity = call.data.get("entity_id")
            if data_entity is not None:
                entity_id = data_entity
                _LOGGER.debug("Got entity_id from data: %s", entity_id)
        
        # Способ 3: Если пришел как список
        if isinstance(entity_id, list):
            if entity_id:
                entity_id = entity_id[0]
                _LOGGER.debug("Entity_id was list, using first: %s", entity_id)
            else:
                entity_id = None
        
        if not entity_id:
            _LOGGER.error("❌ No entity_id provided for record_with_osd service")
            return
        
        _LOGGER.info("🔍 Searching for exact match: %s", entity_id)
        
        duration = call.data.get("duration")
        if not duration:
            _LOGGER.error("No duration provided for record_with_osd service")
            return
        
        # Пробуем преобразовать duration в int
        try:
            duration = int(duration)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid duration value: %s", duration)
            return
            
        template = call.data.get("template", DEFAULT_OSD_TEMPLATE)
        position = call.data.get("position", DEFAULT_OSD_POSITION)
        font_size = call.data.get("font_size", DEFAULT_OSD_FONT_SIZE)
        color = call.data.get("color", DEFAULT_OSD_COLOR)
        send_telegram = call.data.get("send_telegram", False)
        
        # Ищем точное совпадение
        coordinator = await async_find_coordinator_by_entity_id(entity_id)
        
        if not coordinator:
            _LOGGER.error("❌ No camera found with entity_id: %s", entity_id)
            _LOGGER.error("   Please check that you're using the correct entity_id")
            return
            
        if not hasattr(coordinator, 'recorder'):
            _LOGGER.error("❌ Coordinator has no recorder for %s", entity_id)
            return
        
        _LOGGER.info("✅ Using camera - Name: %s, Host: %s", 
                    coordinator.recorder.camera_name, coordinator.host)
        
        osd_config = {
            "template": template,
            "position": position,
            "font_size": font_size,
            "color": color,
            "bg_color": "black@0.5",
        }
        
        # Записываем видео с OSD
        result = await coordinator.recorder.record_video(
            duration, 
            snapshot_interval=5,
            add_osd=True,
            osd_config=osd_config
        )
        
        if result.get("success") and send_telegram:
            # Отправляем в Telegram
            filepath = Path(result["filepath"])
            caption = f"📹 Запись с OSD\n⏱ {duration} секунд"
            await coordinator.recorder.send_to_telegram(filepath, caption)
            _LOGGER.info("Video with OSD sent to Telegram: %s", result["filename"])
        elif result.get("success"):
            _LOGGER.info("Video with OSD recorded: %s", result["filename"])
        else:
            _LOGGER.error("Failed to record video with OSD: %s", result.get("error"))
        
        _LOGGER.debug("=" * 60)
    
    # Register services only once
    if not hass.services.has_service(DOMAIN, "play_audio"):
        hass.services.async_register(DOMAIN, "play_audio", async_play_audio, schema=PLAY_AUDIO_SCHEMA)
    
    if not hass.services.has_service(DOMAIN, "test_audio"):
        hass.services.async_register(DOMAIN, "test_audio", async_test_audio, schema=TEST_AUDIO_SCHEMA)
    
    if not hass.services.has_service(DOMAIN, "reboot"):
        hass.services.async_register(DOMAIN, "reboot", async_reboot, schema=REBOOT_SCHEMA)
    
    if not hass.services.has_service(DOMAIN, "set_ir_mode"):
        hass.services.async_register(DOMAIN, "set_ir_mode", async_set_ir_mode, schema=SET_IR_MODE_SCHEMA)
    
    if not hass.services.has_service(DOMAIN, "scan_devices"):
        hass.services.async_register(DOMAIN, "scan_devices", async_scan_devices, schema=SCAN_DEVICES_SCHEMA)
    
    if not hass.services.has_service(DOMAIN, "start_recording"):
        hass.services.async_register(DOMAIN, "start_recording", async_start_recording, schema=START_RECORDING_SCHEMA)

    if not hass.services.has_service(DOMAIN, "stop_recording"):
        hass.services.async_register(DOMAIN, "stop_recording", async_stop_recording, schema=STOP_RECORDING_SCHEMA)

    if not hass.services.has_service(DOMAIN, "timed_recording"):
        hass.services.async_register(DOMAIN, "timed_recording", async_timed_recording, schema=TIMED_RECORDING_SCHEMA)

    if not hass.services.has_service(DOMAIN, "get_recordings"):
        hass.services.async_register(DOMAIN, "get_recordings", async_get_recordings, schema=GET_RECORDINGS_SCHEMA)

    if not hass.services.has_service(DOMAIN, "delete_recording"):
        hass.services.async_register(DOMAIN, "delete_recording", async_delete_recording, schema=DELETE_RECORDING_SCHEMA)

    if not hass.services.has_service(DOMAIN, "record_and_send_telegram"):
        hass.services.async_register(DOMAIN, "record_and_send_telegram", async_record_and_send_telegram, schema=RECORD_AND_SEND_TELEGRAM_SCHEMA)

    if not hass.services.has_service(DOMAIN, "diagnose_rtsp"):
        hass.services.async_register(DOMAIN, "diagnose_rtsp", async_diagnose_rtsp, schema=DIAGNOSE_RTSP_SCHEMA)

    if not hass.services.has_service(DOMAIN, "diagnose_telegram"):
        hass.services.async_register(DOMAIN, "diagnose_telegram", async_diagnose_telegram, schema=DIAGNOSE_TELEGRAM_SCHEMA)

    if not hass.services.has_service(DOMAIN, "test_telegram"):
        hass.services.async_register(DOMAIN, "test_telegram", async_test_telegram, schema=TEST_TELEGRAM_SCHEMA)

    # Register video playback services
    if not hass.services.has_service(DOMAIN, "get_recordings_stats"):
        hass.services.async_register(
            DOMAIN,
            "get_recordings_stats",
            async_get_recordings_stats,
            schema=GET_RECORDINGS_STATS_SCHEMA
        )

    if not hass.services.has_service(DOMAIN, "delete_all_recordings"):
        hass.services.async_register(
            DOMAIN,
            "delete_all_recordings",
            async_delete_all_recordings,
            schema=DELETE_ALL_RECORDINGS_SCHEMA
        )

    if not hass.services.has_service(DOMAIN, "get_video_thumbnail"):
        hass.services.async_register(
            DOMAIN,
            "get_video_thumbnail",
            async_get_video_thumbnail,
            schema=GET_VIDEO_THUMBNAIL_SCHEMA
        )

    # Register OSD recording service
    if not hass.services.has_service(DOMAIN, "record_with_osd"):
        hass.services.async_register(
            DOMAIN,
            "record_with_osd",
            async_record_with_osd,
            schema=RECORD_WITH_OSD_SCHEMA
        )

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    if not hass.data[DOMAIN] or (len(hass.data[DOMAIN]) == 1 and "config" in hass.data[DOMAIN]):
        services = [
            "play_audio", "test_audio", "reboot", "set_ir_mode", "scan_devices",
            "start_recording", "stop_recording", "timed_recording", "get_recordings",
            "delete_recording", "record_and_send_telegram", "diagnose_rtsp", 
            "diagnose_telegram", "test_telegram", "get_recordings_stats",
            "delete_all_recordings", "get_video_thumbnail", "record_with_osd", "list_fonts"
        ]
        for service in services:
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
    
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)
    
    if config_entry.version == 1:
        return True
    
    return False

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    try:
        device_registry = dr.async_get(hass)
        device_registry.async_clear_config_entry(entry.entry_id)
    except Exception as err:
        _LOGGER.debug("Error removing device registry entry: %s", err)

class OpenIPCDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OpenIPC data."""

    def __init__(self, hass, entry):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.data.get('name', entry.data[CONF_HOST])}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.rtsp_port = entry.data.get(CONF_RTSP_PORT, 554)
        
        self.session = async_get_clientsession(hass)
        self.auth = aiohttp.BasicAuth(self.username, self.password)
        
        # Cache for API responses
        self._cache = {}
        self._cache_time = {}
        
        # Инициализируем recorder
        camera_name = entry.data.get('name', 'OpenIPC Camera')
        self.recorder = OpenIPCRecorder(
            hass,
            self.host,
            self.port,
            self.username,
            self.password,
            camera_name
        )
        
        # Атрибуты для записи
        self.recording_duration = 60
        self._recording_task = None
        self._recording_end_time = None
        self._ha_recording_task = None

    async def _async_update_data(self):
        """Fetch data from camera."""
        try:
            async with async_timeout.timeout(10):
                _LOGGER.debug("Attempting to fetch data from camera %s", self.host)
                
                config_data = await self._get_json_config()
                metrics_data = await self._get_metrics()
                status_data = await self._get_camera_status()
                recording_status = await self.async_get_recording_status()
                
                parsed_data = self._parse_camera_data(config_data, metrics_data, status_data)
                
                if recording_status:
                    parsed_data["recording_status"] = recording_status.get("recording", False)
                    parsed_data["recording_remaining"] = recording_status.get("remaining", 0)
                    parsed_data["recording_end_time"] = recording_status.get("end_time", 0)
                
                data = {
                    "config": config_data,
                    "metrics": metrics_data,
                    "status": status_data,
                    "recording": recording_status,
                    "parsed": parsed_data,
                    "available": True,
                    "last_update": self.hass.loop.time(),
                }
                
                return data
                
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout fetching camera data from %s", self.host)
            if self.data:
                return {**self.data, "available": False}
            raise UpdateFailed(f"Timeout connecting to camera {self.host}")
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                _LOGGER.error("Authentication failed for camera %s", self.host)
                if self.data:
                    return {**self.data, "available": False}
                raise UpdateFailed(f"Authentication failed for camera {self.host}")
            else:
                _LOGGER.error("HTTP error %d from %s", err.status, self.host)
                if self.data:
                    return {**self.data, "available": False}
                raise UpdateFailed(f"HTTP error {err.status} from camera {self.host}")
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("Connection error for camera %s: %s", self.host, err)
            if self.data:
                return {**self.data, "available": False}
            raise UpdateFailed(f"Cannot connect to camera {self.host}")
        except Exception as err:
            _LOGGER.error("Error updating data from %s: %s", self.host, err)
            if self.data:
                return {**self.data, "available": False}
            raise UpdateFailed(f"Error communicating with camera {self.host}: {err}")

    def _parse_camera_data(self, config, metrics, status):
        """Parse data from JSON config, Prometheus metrics and HTML status."""
        parsed = {}
        
        if config and isinstance(config, dict):
            if "video0" in config:
                video = config["video0"]
                if "fps" in video:
                    parsed["fps"] = video["fps"]
                if "bitrate" in video:
                    parsed["bitrate"] = video["bitrate"]
                if "size" in video:
                    parsed["resolution"] = video["size"]
            
            if "system" in config:
                system = config["system"]
                if "logLevel" in system:
                    parsed["log_level"] = system["logLevel"]
            
            if "nightMode" in config:
                night = config["nightMode"]
                parsed["night_mode_enabled"] = night.get("colorToGray", False)
                parsed["ir_cut_pins"] = f"{night.get('irCutPin1', 'N/A')}/{night.get('irCutPin2', 'N/A')}"
            
            if "motionDetect" in config:
                motion = config["motionDetect"]
                parsed["motion_enabled"] = motion.get("enabled", False)
                parsed["motion_sensitivity"] = motion.get("sensitivity", 0)
            
            if "audio" in config:
                audio = config["audio"]
                parsed["audio_enabled"] = audio.get("enabled", False)
                parsed["audio_codec"] = audio.get("codec", "unknown")
                parsed["speaker_enabled"] = audio.get("outputEnabled", False)
            
            if "records" in config:
                records = config["records"]
                parsed["recording_enabled"] = records.get("enabled", False)
                parsed["recording_path"] = records.get("path", "")
        
        if metrics and isinstance(metrics, dict):
            if "node_hwmon_temp_celsius" in metrics:
                parsed["cpu_temp"] = metrics["node_hwmon_temp_celsius"]
            
            if "isp_fps" in metrics:
                parsed["isp_fps"] = metrics["isp_fps"]
            
            if "night_enabled" in metrics:
                parsed["night_mode_enabled_metrics"] = metrics["night_enabled"] == 1
            
            if "ircut_enabled" in metrics:
                parsed["ircut_enabled_metrics"] = metrics["ircut_enabled"] == 1
            
            if "light_enabled" in metrics:
                parsed["light_enabled_metrics"] = metrics["light_enabled"] == 1
            
            if "node_boot_time_seconds" in metrics:
                boot_time = metrics["node_boot_time_seconds"]
                current_time = time.time()
                uptime_seconds = int(current_time - boot_time)
                
                days = uptime_seconds // 86400
                hours = (uptime_seconds % 86400) // 3600
                minutes = (uptime_seconds % 3600) // 60
                seconds = uptime_seconds % 60
                
                if days > 0:
                    parsed["uptime"] = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    parsed["uptime"] = f"{hours}h {minutes}m {seconds}s"
                else:
                    parsed["uptime"] = f"{minutes}m {seconds}s"
                
                parsed["uptime_seconds"] = uptime_seconds
            
            if "node_uname_info" in metrics:
                uname = metrics.get("node_uname_info", {})
                if "nodename" in uname:
                    parsed["hostname"] = uname["nodename"]
                if "machine" in uname:
                    parsed["architecture"] = uname["machine"]
                if "release" in uname:
                    parsed["kernel"] = uname["release"]
            
            if "node_memory_MemTotal_bytes" in metrics:
                parsed["mem_total"] = metrics["node_memory_MemTotal_bytes"] / 1024 / 1024
            if "node_memory_MemFree_bytes" in metrics:
                parsed["mem_free"] = metrics["node_memory_MemFree_bytes"] / 1024 / 1024
            if "node_memory_MemAvailable_bytes" in metrics:
                parsed["mem_available"] = metrics["node_memory_MemAvailable_bytes"] / 1024 / 1024
            
            if "node_network_receive_bytes_total" in metrics:
                net = metrics.get("node_network_receive_bytes_total", {})
                if "eth0" in net:
                    parsed["network_rx_bytes"] = net["eth0"]
            if "node_network_transmit_bytes_total" in metrics:
                net = metrics.get("node_network_transmit_bytes_total", {})
                if "eth0" in net:
                    parsed["network_tx_bytes"] = net["eth0"]
            
            if "http_requests_total" in metrics:
                parsed["http_requests"] = metrics["http_requests_total"]
            if "jpeg_requests_total" in metrics:
                parsed["jpeg_requests"] = metrics["jpeg_requests_total"]
        
        if status and isinstance(status, dict) and "raw" in status:
            raw = status["raw"]
            
            if "uptime" not in parsed:
                uptime_match = re.search(r'<tr>\s*<th[^>]*>Uptime\s*</th>\s*<td[^>]*>([^<]+)</td>\s*</tr>', raw, re.IGNORECASE)
                if uptime_match:
                    parsed["uptime"] = uptime_match.group(1).strip()
            
            if "cpu_temp" not in parsed:
                temp_match = re.search(r'<tr>\s*<th[^>]*>CPU Temp\s*</th>\s*<td[^>]*>([0-9.]+)\s*°C</td>\s*</tr>', raw, re.IGNORECASE)
                if temp_match:
                    parsed["cpu_temp"] = temp_match.group(1)
            
            if "model" not in parsed:
                model_match = re.search(r'<tr>\s*<th[^>]*>Model\s*</th>\s*<td[^>]*>([^<]+)</td>\s*</tr>', raw, re.IGNORECASE)
                if model_match:
                    parsed["model"] = model_match.group(1).strip()
            
            if "firmware" not in parsed:
                fw_match = re.search(r'<tr>\s*<th[^>]*>Firmware\s*</th>\s*<td[^>]*>([^<]+)</td>\s*</tr>', raw, re.IGNORECASE)
                if fw_match:
                    parsed["firmware"] = fw_match.group(1).strip()
        
        return parsed

    async def _get_json_config(self):
        """Get JSON configuration from camera."""
        url = f"http://{self.host}:{self.port}{MAJESTIC_CONFIG}"
        try:
            async with self.session.get(url, auth=self.auth, timeout=5) as response:
                if response.status == 200:
                    try:
                        return await response.json()
                    except:
                        return {}
                return {}
        except:
            return {}

    async def _get_metrics(self):
        """Get Prometheus metrics from camera."""
        url = f"http://{self.host}:{self.port}{METRICS_ENDPOINT}"
        try:
            async with self.session.get(url, auth=self.auth, timeout=5) as response:
                if response.status == 200:
                    text = await response.text()
                    return self._parse_metrics(text)
                return {}
        except:
            return {}

    def _parse_metrics(self, text):
        """Parse Prometheus metrics format."""
        metrics = {}
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '{' in line and '}' in line:
                name_part = line[:line.index('{')]
                labels_part = line[line.index('{')+1:line.index('}')]
                value_part = line[line.index('}')+1:].strip()
                
                labels = {}
                for label in labels_part.split(','):
                    if '=' in label:
                        k, v = label.split('=', 1)
                        labels[k.strip()] = v.strip().strip('"')
                
                try:
                    value = float(value_part)
                except:
                    continue
                
                if name_part not in metrics:
                    metrics[name_part] = {}
                
                if len(labels) == 1 and 'device' in labels:
                    metrics[name_part][labels['device']] = value
                else:
                    label_key = ','.join([f"{k}={v}" for k, v in labels.items()])
                    if name_part not in metrics:
                        metrics[name_part] = {}
                    metrics[name_part][label_key] = value
            else:
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    try:
                        value = float(parts[1])
                        metrics[name] = value
                    except:
                        continue
        
        return metrics

    async def _get_camera_status(self):
        """Get camera status from HTML endpoint."""
        url = f"http://{self.host}:{self.port}{API_STATUS}"
        return await self._fetch_url(url)

    async def _fetch_url(self, url):
        """Fetch URL with error handling."""
        try:
            async with self.session.get(url, auth=self.auth, timeout=5) as response:
                if response.status == 200:
                    try:
                        text = await response.text(encoding='utf-8')
                        return {"raw": text, "status": response.status}
                    except:
                        try:
                            text = await response.text(encoding='latin-1')
                            return {"raw": text, "status": response.status}
                        except:
                            return {}
                return {"status": response.status}
        except:
            return {}

    async def async_send_command(self, command, params=None):
        """Send command to camera."""
        url = f"http://{self.host}:{self.port}{command}"
        if params:
            url += f"?{params}"
        try:
            async with self.session.get(url, auth=self.auth, timeout=5) as response:
                return response.status == 200
        except:
            return False

    async def async_set_night_mode(self, mode: str):
        """Set night mode (on/off/auto)."""
        if mode == "on":
            return await self.async_send_command("/night/on")
        elif mode == "off":
            return await self.async_send_command("/night/off")
        elif mode == "auto":
            return await self.async_send_command("/night/auto")
        return False

    async def async_start_recording(self):
        """Start recording on camera SD card."""
        _LOGGER.info("Starting recording on camera %s", self.host)
        
        endpoints = [
            RECORD_START,
            "/cgi-bin/record.cgi?action=start",
            "/api/v1/record?action=start",
        ]
        
        for endpoint in endpoints:
            if await self.async_send_command(endpoint):
                _LOGGER.info("Recording started via %s", endpoint)
                self._recording_end_time = None
                return True
        
        _LOGGER.error("Failed to start recording")
        return False

    async def async_stop_recording(self):
        """Stop recording on camera SD card."""
        _LOGGER.info("Stopping recording on camera %s", self.host)
        
        if self._recording_task:
            self._recording_task.cancel()
            self._recording_task = None
        
        if self._ha_recording_task and not self._ha_recording_task.done():
            self._ha_recording_task.cancel()
        
        endpoints = [
            RECORD_STOP,
            "/cgi-bin/record.cgi?action=stop",
            "/api/v1/record?action=stop",
        ]
        
        for endpoint in endpoints:
            if await self.async_send_command(endpoint):
                _LOGGER.info("Recording stopped via %s", endpoint)
                self._recording_end_time = None
                return True
        
        _LOGGER.error("Failed to stop recording")
        return False

    async def async_record_to_ha_media(self, duration: int, method: str = "snapshots") -> dict:
        """Record video directly to Home Assistant media folder."""
        _LOGGER.info("Starting HA media recording for %d seconds using %s", duration, method)
        
        if method == "rtsp":
            result = await self.recorder.record_rtsp_stream(duration, "main", False)
        else:
            result = await self.recorder.record_video(duration)
        
        if result.get("success"):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"📹 Запись с камеры {self.recorder.camera_name}",
                    "message": f"✅ Видео сохранено:\n"
                              f"📁 {result['filename']}\n"
                              f"⏱ Длительность: {duration} сек\n"
                              f"📊 Размер: {result['size'] / 1024:.1f} KB\n"
                              f"📍 {result['url']}",
                    "notification_id": f"openipc_recording_{self.entry.entry_id}"
                },
                blocking=True
            )
        
        return result

    async def async_start_timed_recording(self, duration: int, save_to_ha: bool = True, method: str = "snapshots"):
        """Start recording for specified duration."""
        _LOGGER.info("Starting %d second recording on camera %s (save_to_ha=%s)", 
                     duration, self.host, save_to_ha)
        
        if save_to_ha:
            if self._ha_recording_task and not self._ha_recording_task.done():
                self._ha_recording_task.cancel()
            
            self._ha_recording_task = asyncio.create_task(
                self.async_record_to_ha_media(duration, method)
            )
            
            self._recording_end_time = self.hass.loop.time() + duration
            return True
        else:
            await self.async_stop_recording()
            await asyncio.sleep(1)
            
            duration_url = RECORD_MANUAL.format(duration)
            if await self.async_send_command(duration_url):
                _LOGGER.info("Timed recording started via %s", duration_url)
                self._recording_end_time = self.hass.loop.time() + duration
                return True
            
            if await self.async_start_recording():
                self._recording_end_time = self.hass.loop.time() + duration
                
                async def stop_after_delay():
                    try:
                        await asyncio.sleep(duration)
                        await self.async_stop_recording()
                    except asyncio.CancelledError:
                        _LOGGER.debug("Recording timer cancelled")
                
                self._recording_task = asyncio.create_task(stop_after_delay())
                return True
            
            return False

    async def async_get_recording_status(self):
        """Get recording status."""
        endpoints = [
            RECORD_STATUS,
            "/cgi-bin/record.cgi?action=status",
            "/api/v1/record/status",
        ]
        
        for endpoint in endpoints:
            try:
                url = f"http://{self.host}:{self.port}{endpoint}"
                async with self.session.get(url, auth=self.auth, timeout=3) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            return data
                        except:
                            text = await response.text()
                            if "recording" in text.lower():
                                return {
                                    "recording": "active" in text.lower() or "true" in text.lower(),
                                    "raw": text
                                }
            except:
                continue
        
        if self._recording_end_time:
            remaining = self._recording_end_time - self.hass.loop.time()
            if remaining > 0:
                return {
                    "recording": True,
                    "remaining": int(remaining),
                    "end_time": self._recording_end_time,
                }
        
        return {"recording": False}

    async def async_record_and_send_telegram(self, duration: int, method: str = "snapshots",
                                            caption: str = None, chat_id: str = None) -> dict:
        """
        Record video and send to Telegram.
        """
        _LOGGER.info("Recording and sending to Telegram for %d seconds", duration)
        
        result = await self.recorder.record_and_send_to_telegram(
            duration, method, caption, chat_id
        )
        
        if result.get("success") and result.get("telegram_sent"):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"📹 Запись с камеры {self.recorder.camera_name}",
                    "message": f"✅ Видео сохранено и отправлено в Telegram!\n"
                              f"📁 {result['filename']}\n"
                              f"⏱ Длительность: {duration} сек\n"
                              f"📊 Размер: {result['size'] / 1024:.1f} KB",
                    "notification_id": f"openipc_telegram_{self.entry.entry_id}"
                },
                blocking=True
            )
        elif result.get("success"):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"📹 Запись с камеры {self.recorder.camera_name}",
                    "message": f"✅ Видео сохранено, но НЕ отправлено в Telegram.\n"
                              f"📁 {result['filename']}\n"
                              f"⏱ Длительность: {duration} сек",
                    "notification_id": f"openipc_telegram_{self.entry.entry_id}"
                },
                blocking=True
            )
        
        return result

    async def async_diagnose_rtsp(self):
        """Diagnose RTSP stream."""
        if hasattr(self, 'recorder'):
            results = await self.recorder.diagnose_rtsp()
            
            message = "📹 **RTSP Diagnostic Results**\n\n"
            working_paths = []
            
            for path, result in results.items():
                status = "✅" if result["success"] else "❌"
                message += f"{status} `{path}`\n"
                if result["success"]:
                    working_paths.append(path)
                elif result.get("error"):
                    message += f"   Error: {result['error'][:100]}\n"
            
            if working_paths:
                message += f"\n**Working paths:**\n"
                for path in working_paths:
                    message += f"- `{path}`\n"
                message += "\n**Recommended path for configuration:**\n"
                message += f"`{working_paths[0]}`"
            else:
                message += "\n❌ No working RTSP paths found!\n"
                message += "\n**Troubleshooting:**\n"
                message += "1. Check if camera is powered on\n"
                message += "2. Verify RTSP port (default 554)\n"
                message += "3. Check firewall settings\n"
                message += "4. Try different stream paths in config\n"
                message += "5. Verify RTSP is enabled in camera settings"
            
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"RTSP Diagnosis - {self.recorder.camera_name}",
                    "message": message,
                    "notification_id": f"openipc_rtsp_diagnose_{self.entry.entry_id}"
                },
                blocking=True
            )
            
            return results
        return None

    async def async_diagnose_telegram(self):
        """Diagnose Telegram configuration."""
        if hasattr(self, 'recorder'):
            results = await self.recorder.diagnose_telegram()
            
            message = f"📱 **Telegram Diagnostic Results for {self.recorder.camera_name}**\n\n"
            message += f"• telegram_bot.send_file: {'✅' if results.get('telegram_bot_service') else '❌'}\n"
            message += f"• notify.telegram_notify: {'✅' if results.get('notify_service') else '❌'}\n"
            message += f"• Bot token configured: {'✅' if results.get('bot_token_configured') else '❌'}\n"
            message += f"• Chat ID configured: {'✅' if results.get('chat_id_configured') else '❌'}\n"
            message += f"• Available services: {results.get('available_services', [])}\n"
            
            if results.get('test_message'):
                message += f"• Test message: {results['test_message']}\n"
            
            message += "\n**Troubleshooting:**\n"
            message += "1. Configure Telegram bot via UI: Settings → Devices & Services → Add Integration → Telegram bot\n"
            message += "2. Add bot token and chat_id to openipc section in configuration.yaml for direct API\n"
            
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Telegram Diagnosis",
                    "message": message,
                    "notification_id": f"openipc_telegram_diagnose_{self.entry.entry_id}"
                },
                blocking=True
            )
            
            return results
        return None

    async def async_test_telegram(self, chat_id: str = None):
        """Test Telegram file send."""
        if hasattr(self, 'recorder'):
            results = await self.recorder.test_telegram_file_send(chat_id)
            return results
        return None
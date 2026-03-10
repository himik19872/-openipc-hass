"""Services for OpenIPC integration."""
import logging
import voluptuous as vol
import aiohttp
from functools import partial

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
import homeassistant.helpers.service as service_helper

from .const import DOMAIN
from .helpers import find_coordinator_by_entity_id, find_media_player, find_button, find_switch

_LOGGER = logging.getLogger(__name__)

# Схемы сервисов
START_QR_SCAN_SCHEMA = vol.Schema({
    vol.Required('entity_id'): cv.entity_id,
    vol.Optional('expected_code', default='a4625vol'): cv.string,
    vol.Optional('timeout', default=300): vol.Coerce(int),
})

# Список всех сервисов для удаления при выгрузке
ALL_SERVICES = [
    "play_audio", "test_audio", "reboot", "set_ir_mode", "scan_devices",
    "start_recording", "stop_recording", "timed_recording", "get_recordings",
    "delete_recording", "record_and_send_telegram", "diagnose_rtsp", 
    "diagnose_telegram", "test_telegram", "get_recordings_stats",
    "delete_all_recordings", "get_video_thumbnail", "record_with_osd", "list_fonts",
    "beward_open_door", "beward_play_beep", "beward_play_ringtone", 
    "beward_enable_audio", "beward_test",
    "lnpr_get_list", "lnpr_add_plate", "lnpr_delete_plate", "lnpr_export_events",
    "lnpr_clear_events", "lnpr_clear_list", "lnpr_get_picture",
    "ptz_move", "ptz_goto_preset", "ptz_set_preset",
    "qr_scan", "qr_set_mode", "qr_stop",
    "start_qr_scan",
]

async def async_register_services(hass: HomeAssistant) -> None:
    """Register all services for OpenIPC."""
    
    from .services_impl import (
        async_play_audio, async_test_audio, async_reboot, async_set_ir_mode,
        async_scan_devices, async_start_recording, async_stop_recording,
        async_timed_recording, async_get_recordings, async_delete_recording,
        async_record_and_send_telegram, async_diagnose_rtsp, async_diagnose_telegram,
        async_test_telegram, async_get_recordings_stats, async_delete_all_recordings,
        async_get_video_thumbnail, async_record_with_osd, async_list_fonts,
        async_beward_open_door, async_beward_play_beep, async_beward_play_ringtone,
        async_beward_enable_audio, async_beward_test,
        async_lnpr_get_list, async_lnpr_add_plate, async_lnpr_delete_plate,
        async_lnpr_export_events, async_lnpr_clear_events, async_lnpr_clear_list,
        async_lnpr_get_picture, async_ptz_move, async_ptz_goto_preset,
        async_ptz_set_preset, async_qr_scan, async_qr_set_mode, async_qr_stop,
        async_start_qr_scan
    )
    
    from .service_schemas import (
        PLAY_AUDIO_SCHEMA, TEST_AUDIO_SCHEMA, REBOOT_SCHEMA, SET_IR_MODE_SCHEMA,
        SCAN_DEVICES_SCHEMA, START_RECORDING_SCHEMA, STOP_RECORDING_SCHEMA,
        TIMED_RECORDING_SCHEMA, GET_RECORDINGS_SCHEMA, DELETE_RECORDING_SCHEMA,
        RECORD_AND_SEND_TELEGRAM_SCHEMA, DIAGNOSE_RTSP_SCHEMA, DIAGNOSE_TELEGRAM_SCHEMA,
        TEST_TELEGRAM_SCHEMA, GET_RECORDINGS_STATS_SCHEMA, DELETE_ALL_RECORDINGS_SCHEMA,
        GET_VIDEO_THUMBNAIL_SCHEMA, RECORD_WITH_OSD_SCHEMA,
        BEWARD_OPEN_DOOR_SCHEMA, BEWARD_PLAY_BEEP_SCHEMA, BEWARD_PLAY_RINGTONE_SCHEMA,
        BEWARD_ENABLE_AUDIO_SCHEMA, BEWARD_TEST_SCHEMA,
        LNPR_GET_LIST_SCHEMA, LNPR_ADD_PLATE_SCHEMA, LNPR_DELETE_PLATE_SCHEMA,
        LNPR_EXPORT_EVENTS_SCHEMA, LNPR_CLEAR_EVENTS_SCHEMA, LNPR_CLEAR_LIST_SCHEMA,
        LNPR_GET_PICTURE_SCHEMA, PTZ_MOVE_SCHEMA, PTZ_GOTO_PRESET_SCHEMA,
        PTZ_SET_PRESET_SCHEMA, QR_SCAN_SCHEMA, QR_SET_MODE_SCHEMA, QR_STOP_SCHEMA,
        START_QR_SCAN_SCHEMA
    )
    
    # Регистрируем сервисы через правильную обертку
    # Для сервисов, которым нужен hass, создаем обертку
    
    async def async_start_qr_scan_wrapper(call: ServiceCall) -> None:
        """Wrapper for start_qr_scan service."""
        await async_start_qr_scan(call, hass)
    
    hass.services.async_register(
        DOMAIN,
        "start_qr_scan",
        async_start_qr_scan_wrapper,
        schema=START_QR_SCAN_SCHEMA,
    )
    
    # Регистрируем остальные сервисы
    services = [
        ("play_audio", async_play_audio, PLAY_AUDIO_SCHEMA),
        ("test_audio", async_test_audio, TEST_AUDIO_SCHEMA),
        ("reboot", async_reboot, REBOOT_SCHEMA),
        ("set_ir_mode", async_set_ir_mode, SET_IR_MODE_SCHEMA),
        ("scan_devices", async_scan_devices, SCAN_DEVICES_SCHEMA),
        ("start_recording", async_start_recording, START_RECORDING_SCHEMA),
        ("stop_recording", async_stop_recording, STOP_RECORDING_SCHEMA),
        ("timed_recording", async_timed_recording, TIMED_RECORDING_SCHEMA),
        ("get_recordings", async_get_recordings, GET_RECORDINGS_SCHEMA),
        ("delete_recording", async_delete_recording, DELETE_RECORDING_SCHEMA),
        ("record_and_send_telegram", async_record_and_send_telegram, RECORD_AND_SEND_TELEGRAM_SCHEMA),
        ("diagnose_rtsp", async_diagnose_rtsp, DIAGNOSE_RTSP_SCHEMA),
        ("diagnose_telegram", async_diagnose_telegram, DIAGNOSE_TELEGRAM_SCHEMA),
        ("test_telegram", async_test_telegram, TEST_TELEGRAM_SCHEMA),
        ("get_recordings_stats", async_get_recordings_stats, GET_RECORDINGS_STATS_SCHEMA),
        ("delete_all_recordings", async_delete_all_recordings, DELETE_ALL_RECORDINGS_SCHEMA),
        ("get_video_thumbnail", async_get_video_thumbnail, GET_VIDEO_THUMBNAIL_SCHEMA),
        ("record_with_osd", async_record_with_osd, RECORD_WITH_OSD_SCHEMA),
        ("list_fonts", async_list_fonts, None),
        ("beward_open_door", async_beward_open_door, BEWARD_OPEN_DOOR_SCHEMA),
        ("beward_play_beep", async_beward_play_beep, BEWARD_PLAY_BEEP_SCHEMA),
        ("beward_play_ringtone", async_beward_play_ringtone, BEWARD_PLAY_RINGTONE_SCHEMA),
        ("beward_enable_audio", async_beward_enable_audio, BEWARD_ENABLE_AUDIO_SCHEMA),
        ("beward_test", async_beward_test, BEWARD_TEST_SCHEMA),
        ("lnpr_get_list", async_lnpr_get_list, LNPR_GET_LIST_SCHEMA),
        ("lnpr_add_plate", async_lnpr_add_plate, LNPR_ADD_PLATE_SCHEMA),
        ("lnpr_delete_plate", async_lnpr_delete_plate, LNPR_DELETE_PLATE_SCHEMA),
        ("lnpr_export_events", async_lnpr_export_events, LNPR_EXPORT_EVENTS_SCHEMA),
        ("lnpr_clear_events", async_lnpr_clear_events, LNPR_CLEAR_EVENTS_SCHEMA),
        ("lnpr_clear_list", async_lnpr_clear_list, LNPR_CLEAR_LIST_SCHEMA),
        ("lnpr_get_picture", async_lnpr_get_picture, LNPR_GET_PICTURE_SCHEMA),
        ("ptz_move", async_ptz_move, PTZ_MOVE_SCHEMA),
        ("ptz_goto_preset", async_ptz_goto_preset, PTZ_GOTO_PRESET_SCHEMA),
        ("ptz_set_preset", async_ptz_set_preset, PTZ_SET_PRESET_SCHEMA),
        ("qr_scan", async_qr_scan, QR_SCAN_SCHEMA),
        ("qr_set_mode", async_qr_set_mode, QR_SET_MODE_SCHEMA),
        ("qr_stop", async_qr_stop, QR_STOP_SCHEMA),
    ]
    
    for service_name, service_func, schema in services:
        if not hass.services.has_service(DOMAIN, service_name):
            # Для функций, которым не нужен hass, регистрируем напрямую
            if service_name in ["play_audio", "test_audio", "reboot", "set_ir_mode", 
                               "scan_devices", "start_recording", "stop_recording",
                               "timed_recording", "get_recordings", "delete_recording",
                               "record_and_send_telegram", "diagnose_rtsp", 
                               "diagnose_telegram", "test_telegram", "get_recordings_stats",
                               "delete_all_recordings", "get_video_thumbnail", 
                               "record_with_osd", "list_fonts", "beward_open_door",
                               "beward_play_beep", "beward_play_ringtone",
                               "beward_enable_audio", "beward_test", "lnpr_get_list",
                               "lnpr_add_plate", "lnpr_delete_plate", "lnpr_export_events",
                               "lnpr_clear_events", "lnpr_clear_list", "lnpr_get_picture",
                               "ptz_move", "ptz_goto_preset", "ptz_set_preset",
                               "qr_scan", "qr_set_mode", "qr_stop"]:
                # Для этих функций нужно создать обертку с hass
                async def create_wrapper(func, service_call):
                    await func(service_call, hass)
                
                wrapper = lambda call, f=service_func: f(call, hass)
                hass.services.async_register(DOMAIN, service_name, wrapper, schema=schema)
            else:
                hass.services.async_register(DOMAIN, service_name, service_func, schema=schema)
            _LOGGER.debug("Registered service: %s", service_name)
    
    _LOGGER.info("✅ All services registered")

async def async_remove_services(hass: HomeAssistant) -> None:
    """Remove all services when last entry is unloaded."""
    for service in ALL_SERVICES:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
            _LOGGER.debug("Removed service: %s", service)
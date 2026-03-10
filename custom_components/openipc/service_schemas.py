"""Service schemas for OpenIPC integration."""
import voluptuous as vol
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import config_validation as cv

from .const import OSD_POSITIONS, OSD_COLORS, DEFAULT_OSD_TEMPLATE

# Basic schemas
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

# Recording schemas
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

# Diagnostic schemas
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

# Recording stats schemas
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

# OSD recording schema
RECORD_WITH_OSD_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("duration"): vol.Coerce(int),
    vol.Optional("template", default=DEFAULT_OSD_TEMPLATE): cv.string,
    vol.Optional("position", default="top_left"): vol.In(OSD_POSITIONS.keys()),
    vol.Optional("font_size", default=24): vol.Coerce(int),
    vol.Optional("color", default="white"): vol.In(OSD_COLORS.keys()),
    vol.Optional("send_telegram", default=False): cv.boolean,
})

# LNPR schemas
LNPR_GET_LIST_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

LNPR_ADD_PLATE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("number"): cv.string,
    vol.Optional("begin"): cv.string,
    vol.Optional("end"): cv.string,
    vol.Optional("notify", default=False): cv.boolean,
    vol.Optional("note"): cv.string,
})

LNPR_DELETE_PLATE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("number"): cv.string,
})

LNPR_EXPORT_EVENTS_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("days", default=7): vol.Coerce(int),
})

LNPR_CLEAR_EVENTS_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

LNPR_CLEAR_LIST_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

LNPR_GET_PICTURE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("time"): cv.string,
    vol.Required("filename"): cv.string,
})

# Beward schemas
BEWARD_OPEN_DOOR_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("main", default=True): cv.boolean,
})

BEWARD_PLAY_BEEP_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

BEWARD_PLAY_RINGTONE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

BEWARD_ENABLE_AUDIO_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("enable"): cv.boolean,
})

BEWARD_TEST_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

# PTZ schemas
PTZ_MOVE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("direction"): vol.In(["up", "down", "left", "right", "up-left", "up-right", "down-left", "down-right", "in", "out"]),
    vol.Optional("speed", default=50): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
})

PTZ_GOTO_PRESET_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("preset_id"): vol.Coerce(int),
})

PTZ_SET_PRESET_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("preset_id"): vol.Coerce(int),
    vol.Optional("name"): cv.string,
})

# QR schemas
QR_SCAN_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional("timeout", default=30): vol.Coerce(int),
})

QR_SET_MODE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required("mode"): vol.In(["disabled", "single", "periodic", "continuous"]),
})

QR_STOP_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
})

# QR continuous scan schema
START_QR_SCAN_SCHEMA = vol.Schema({
    vol.Required('entity_id'): cv.entity_id,
    vol.Optional('expected_code', default='a4625vol'): cv.string,
    vol.Optional('timeout', default=300): vol.Coerce(int),
})
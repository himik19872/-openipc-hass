"""Constants for OpenIPC integration."""
from homeassistant.const import Platform

DOMAIN = "openipc"
PLATFORMS = ["camera", "binary_sensor", "sensor", "switch", "button", "media_player", "select"]

# Default values
DEFAULT_PORT = 80
DEFAULT_RTSP_PORT = 554
DEFAULT_USERNAME = "root"
DEFAULT_SCAN_INTERVAL = 30

# Configuration
CONF_RTSP_PORT = "rtsp_port"
CONF_STREAM_PROFILE = "stream_profile"
CONF_RECORD_PATH = "record_path"
CONF_RECORD_FORMAT = "record_format"

# Device types
CONF_DEVICE_TYPE = "device_type"
DEVICE_TYPE_OPENIPC = "openipc"
DEVICE_TYPE_BEWARD = "beward"
DEVICE_TYPE_VIVOTEK = "vivotek"

# Media paths
MEDIA_RECORD_PATH = "openipc_recordings"

# Video streams
RTSP_STREAM_MAIN = "/stream=0"
RTSP_STREAM_SUB = "/stream=1"
RTSP_STREAM_JPEG = "/stream=2"
MJPEG_STREAM = "/mjpeg"
MP4_STREAM = "/video.mp4"
HLS_STREAM = "/hls"
MJPEG_HTML = "/mjpeg.html"

# Audio streams
AUDIO_OPUS = "/audio.opus"
AUDIO_M4A = "/audio.m4a"
AUDIO_PCM = "/audio.pcm"
AUDIO_ALAW = "/audio.alaw"
AUDIO_ULAW = "/audio.ulaw"
AUDIO_G711A = "/audio.g711a"
AUDIO_PLAY = "/play_audio"

# Images
IMAGE_JPEG = "/image.jpg"
IMAGE_HEIF = "/image.heif"
IMAGE_YUV420 = "/image.yuv420"

# Night mode control
NIGHT_ON = "/night/on"
NIGHT_OFF = "/night/off"
NIGHT_TOGGLE = "/night/toggle"
NIGHT_IRCUT = "/night/ircut"
NIGHT_LIGHT = "/night/light"

# Recording control
RECORD_START = "/cgi-bin/record.cgi?action=start"
RECORD_STOP = "/cgi-bin/record.cgi?action=stop"
RECORD_STATUS = "/cgi-bin/record.cgi?action=status"
RECORD_MANUAL = "/cgi-bin/record.cgi?action=manual&duration={}"

# Majestic API
MAJESTIC_CONFIG = "/api/v1/config.json"
MAJESTIC_CONFIG_SCHEMA = "/api/v1/config.schema.json"
MAJESTIC_STATUS = "/api/v1/status"
MAJESTIC_RECORD = "/api/v1/record"

# Metrics
METRICS_ENDPOINT = "/metrics"

# Основные эндпоинты для OpenIPC
API_STATUS = "/cgi-bin/status.cgi"
API_SYSTEM_INFO = "/cgi-bin/system_info.cgi"
API_SD_INFO = "/cgi-bin/sd_info.cgi"
API_MOTION_DETECTION = "/cgi-bin/motion_detection.cgi"
API_SET_IR_MODE = "/cgi-bin/ir_cut.cgi?mode={}"
API_REBOOT = "/cgi-bin/reboot.cgi"

# Альтернативные эндпоинты
ALT_API_STATUS = "/cgi-bin/status"
ALT_API_SYSTEM_INFO = "/cgi-bin/system_info"
ALT_API_SD_INFO = "/cgi-bin/sd_info"
ALT_API_MOTION = "/cgi-bin/motion_detection"
ALT_API_REBOOT = "/cgi-bin/reboot"

# LNPR Endpoints (для распознавания номеров)
LNPR_STATE = "/cgi-bin/lnprstate_cgi"
LNPR_LIST = "/cgi-bin/lnpr_cgi?action=list"
LNPR_ADD = "/cgi-bin/lnpr_cgi?action=add"
LNPR_EDIT = "/cgi-bin/lnpr_cgi?action=edit"
LNPR_DELETE = "/cgi-bin/lnpr_cgi?action=remove"
LNPR_CLEAR = "/cgi-bin/lnpr_cgi?action=clear"
LNPR_EXPORT = "/cgi-bin/lnprevent_cgi?action=export"
LNPR_CLEAR_LOG = "/cgi-bin/lnprevent_cgi?action=clear"
LNPR_CURRENT = "/cgi-bin/lnprevent_cgi?action=current"
LNPR_GET_PIC = "/cgi-bin/lnprevent_cgi?action=getpic"

# Сенсоры
SENSOR_TYPES = {
    "uptime_seconds": {"name": "Uptime", "unit": "s", "icon": "mdi:timer"},
    "cpu_temp": {"name": "CPU Temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "sd_free": {"name": "SD Free Space", "unit": "MB", "icon": "mdi:sd"},
    "sd_total": {"name": "SD Total Space", "unit": "MB", "icon": "mdi:sd"},
    "sd_used": {"name": "SD Used Space", "unit": "MB", "icon": "mdi:sd"},
    "wifi_signal": {"name": "WiFi Signal", "unit": "%", "icon": "mdi:wifi"},
    "fps": {"name": "Video FPS", "unit": "fps", "icon": "mdi:video"},
    "isp_fps": {"name": "Sensor FPS", "unit": "fps", "icon": "mdi:camera"},
    "bitrate": {"name": "Bitrate", "unit": "kbps", "icon": "mdi:speedometer"},
    "resolution": {"name": "Resolution", "icon": "mdi:aspect-ratio"},
    "audio_codec": {"name": "Audio Codec", "icon": "mdi:music"},
    "motion_sensitivity": {"name": "Motion Sensitivity", "unit": "", "icon": "mdi:motion-sensor"},
    "mem_total": {"name": "Memory Total", "unit": "MB", "icon": "mdi:memory"},
    "mem_free": {"name": "Memory Free", "unit": "MB", "icon": "mdi:memory"},
    "mem_available": {"name": "Memory Available", "unit": "MB", "icon": "mdi:memory"},
    "network_rx_bytes": {"name": "Network RX", "unit": "B", "icon": "mdi:download"},
    "network_tx_bytes": {"name": "Network TX", "unit": "B", "icon": "mdi:upload"},
    "http_requests": {"name": "HTTP Requests", "unit": "", "icon": "mdi:web"},
    "jpeg_requests": {"name": "JPEG Requests", "unit": "", "icon": "mdi:camera"},
    "majestic_cpu_user": {"name": "Majestic CPU (User)", "unit": "s", "icon": "mdi:cpu-64-bit"},
    "majestic_cpu_system": {"name": "Majestic CPU (System)", "unit": "s", "icon": "mdi:cpu-64-bit"},
    "hostname": {"name": "Hostname", "icon": "mdi:server"},
    "architecture": {"name": "Architecture", "icon": "mdi:cpu-32-bit"},
    "kernel": {"name": "Kernel", "icon": "mdi:linux"},
    "recording_status": {"name": "Recording Status", "icon": "mdi:record-rec"},
    "recording_duration": {"name": "Recording Duration", "unit": "s", "icon": "mdi:timer"},
    "recording_start_time": {"name": "Recording Start Time", "icon": "mdi:clock-start"},
    "record_path": {"name": "Record Path", "icon": "mdi:folder"},
    "record_files": {"name": "Record Files", "icon": "mdi:file-video"},
    "record_last_file": {"name": "Last Recording", "icon": "mdi:video"},
    "recordings_count": {"name": "Total Recordings", "icon": "mdi:counter"},
    "recordings_size": {"name": "Recordings Size", "unit": "MB", "icon": "mdi:database"},
    
    # LNPR сенсоры - ВАЖНО: строковые сенсоры, device_class = None
    "lnpr_last_number": {"name": "Last Plate", "unit": None, "icon": "mdi:car", "device_class": None},
    "lnpr_last_direction": {"name": "Last Direction", "unit": None, "icon": "mdi:arrow-decision", "device_class": None},
    "lnpr_last_time": {"name": "Last Recognition Time", "unit": None, "icon": "mdi:clock", "device_class": None},
    "lnpr_total_today": {"name": "Today Recognitions", "unit": "count", "icon": "mdi:counter", "device_class": None},
    "lnpr_authorized_count": {"name": "Authorized Plates", "unit": "count", "icon": "mdi:format-list-numbered", "device_class": None},
}

# Бинарные сенсоры
BINARY_SENSOR_TYPES = {
    "online": {"name": "Online", "icon": "mdi:connection"},
    "motion": {"name": "Motion", "icon": "mdi:motion-sensor"},
    "recording": {"name": "Recording", "icon": "mdi:record-rec"},
    "night_mode": {"name": "Night Mode", "icon": "mdi:weather-night"},
    "ircut": {"name": "IR Cut", "icon": "mdi:camera-iris"},
    "night_light": {"name": "Night Light", "icon": "mdi:lightbulb-night"},
    "audio_enabled": {"name": "Audio", "icon": "mdi:microphone"},
    "speaker_enabled": {"name": "Speaker", "icon": "mdi:speaker"},
    
    # LNPR бинарные сенсоры
    "lnpr_authorized": {"name": "Authorized Plate", "icon": "mdi:check-circle"},
    "lnpr_unauthorized": {"name": "Unauthorized Plate", "icon": "mdi:alert-circle"},
}

# Переключатели
SWITCH_TYPES = {
    "night_mode": {"name": "Night Mode", "icon": "mdi:weather-night"},
    "ircut": {"name": "IR Cut", "icon": "mdi:camera-iris"},
    "night_light": {"name": "Night Light", "icon": "mdi:lightbulb-night"},
    "recording": {"name": "Recording", "icon": "mdi:record-rec"},
    
    # LNPR переключатели
    "lnpr_enable": {"name": "LNPR Enable", "icon": "mdi:car"},
    "lnpr_free_enter": {"name": "Free Enter Mode", "icon": "mdi:gate"},
    "lnpr_record": {"name": "Record on Recognition", "icon": "mdi:record-rec"},
    "lnpr_ftp": {"name": "FTP on Recognition", "icon": "mdi:cloud-upload"},
}

# Discovery constants
DISCOVERY_PORT = 1900
DISCOVERY_TIMEOUT = 5
DISCOVERY_MAX_DEVICES = 10

# SSDP discovery
SSDP_ST = "urn:schemas-upnp-org:device:Basic:1"
SSDP_MANUFACTURER = "OpenIPC"

# mDNS service types
MDNS_SERVICE = "_http._tcp.local."
MDNS_DEVICE_TYPE = "_openipc._tcp.local."
MDNS_BEWARD = "_beward._tcp.local."

# Broadcast discovery
BROADCAST_PORTS = [80, 8080, 81]
DISCOVERY_ENDPOINTS = [
    "/cgi-bin/status.cgi",
    "/cgi-bin/status",
    "/api/v1/config.json",
    "/metrics",
    "/image.jpg",
]

# Known OpenIPC MAC prefixes
OPENIPC_MAC_PREFIXES = [
    "00:11:22",
    "A0:B1:C2",
]

# OSD Configuration
CONF_OSD_ENABLED = "osd_enabled"
CONF_OSD_TEMPLATE = "osd_template"
CONF_OSD_POSITION = "osd_position"
CONF_OSD_FONT_SIZE = "osd_font_size"
CONF_OSD_COLOR = "osd_color"
CONF_OSD_BG_COLOR = "osd_bg_color"
CONF_OSD_OPACITY = "osd_opacity"

# OSD Positions
OSD_POSITIONS = {
    "top_left": "10:10",
    "top_right": "main_w-text_w-10:10",
    "bottom_left": "10:main_h-text_h-10",
    "bottom_right": "main_w-text_w-10:main_h-text_h-10",
    "center": "(main_w/2-text_w/2):(main_h/2-text_h/2)",
}

# OSD Colors
OSD_COLORS = {
    "white": "white",
    "black": "black",
    "red": "red",
    "green": "green",
    "blue": "blue",
    "yellow": "yellow",
    "cyan": "cyan",
    "magenta": "magenta",
}

# OSD Defaults
DEFAULT_OSD_TEMPLATE = """{camera_name}
{timestamp}
Temp: {cpu_temp}°C
Uptime: {uptime}"""
DEFAULT_OSD_POSITION = "top_left"
DEFAULT_OSD_FONT_SIZE = 24
DEFAULT_OSD_COLOR = "white"
DEFAULT_OSD_BG_COLOR = "black@0.5"
DEFAULT_OSD_OPACITY = 0.7

# Beward specific endpoints
BEWARD_SNAPSHOT = "/cgi-bin/jpg/image.cgi"
BEWARD_MJPEG = "/cgi-bin/video.cgi"
BEWARD_RTSP_MAIN = "/av0_0"
BEWARD_RTSP_SUB = "/av0_1"
BEWARD_OPEN_DOOR = "/cgi-bin/intercom_cgi?action=maindoor"
BEWARD_OPEN_DOOR_ALT = "/cgi-bin/intercom_cgi?action=altdoor"
BEWARD_STATUS = "/cgi-bin/status.cgi"
BEWARD_AUDIO_GET = "/cgi-bin/audio_cgi?action=get"
BEWARD_AUDIO_SET = "/cgi-bin/audio_cgi?action=set"
BEWARD_INTERCOM_STATUS = "/cgi-bin/intercom_cgi?action=status"
BEWARD_INTERCOM_LOCKED = "/cgi-bin/intercom_cgi?action=locked"
BEWARD_SYSTEM_INFO = "/cgi-bin/systeminfo_cgi?action=get"
BEWARD_PLAY_SOUND = "/cgi-bin/intercom_info_cgi?action=play_sound&Type=0"
BEWARD_AUDIO_BEEP = "/cgi-bin/audio_cgi?action=beep"

# Beward LNPR endpoints
BEWARD_LNPR_STATE = "/cgi-bin/lnprstate_cgi"
BEWARD_LNPR_LIST = "/cgi-bin/lnpr_cgi?action=list"
BEWARD_LNPR_ADD = "/cgi-bin/lnpr_cgi?action=add"
BEWARD_LNPR_EDIT = "/cgi-bin/lnpr_cgi?action=edit"
BEWARD_LNPR_DELETE = "/cgi-bin/lnpr_cgi?action=remove"
BEWARD_LNPR_CLEAR = "/cgi-bin/lnpr_cgi?action=clear"
BEWARD_LNPR_EXPORT = "/cgi-bin/lnprevent_cgi?action=export"
BEWARD_LNPR_GET_PIC = "/cgi-bin/lnprevent_cgi?action=getpic"
BEWARD_LNPR_CURRENT = "/cgi-bin/lnprevent_cgi?action=current"

# Vivotek specific endpoints
VIVOTEK_SNAPSHOT = "/cgi-bin/video.jpg"
VIVOTEK_MJPEG = "/cgi-bin/viewer/video.mjpg"
VIVOTEK_RTSP_MAIN = "/live.sdp"
VIVOTEK_RTSP_SUB = "/live2.sdp"

# Beward events
BEWARD_EVENT_MOTION = "motion"
BEWARD_EVENT_SENSOR = "sensor"
BEWARD_EVENT_SOUND = "sound"
BEWARD_EVENT_ONLINE = "online"
BEWARD_EVENT_DOOR_MAIN = "main_door"
BEWARD_EVENT_DOOR_ALT = "alt_door"
BEWARD_EVENT_BUTTON_MAIN = "main_button"
BEWARD_EVENT_BUTTON_ALT = "alt_button"
BEWARD_EVENT_BREAK_IN = "break_in"

# LNPR Events
LNPR_EVENT_RECOGNIZED = "lnpr_recognized"
LNPR_EVENT_AUTHORIZED = "lnpr_authorized"
LNPR_EVENT_UNAUTHORIZED = "lnpr_unauthorized"

# OpenIPC Audio endpoints
OPENIPC_AUDIO_PLAY = "/play_audio"
OPENIPC_AUDIO_PCM = "/audio.pcm"
OPENIPC_AUDIO_ALAW = "/audio.alaw"
OPENIPC_AUDIO_ULAW = "/audio.ulaw"
OPENIPC_AUDIO_G711A = "/audio.g711a"
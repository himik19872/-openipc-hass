"""Data parsers for OpenIPC cameras."""
import logging
import re
import time

_LOGGER = logging.getLogger(__name__)

def parse_camera_data(config, metrics, status):
    """Parse data from JSON config, Prometheus metrics and HTML status."""
    parsed = {}
    
    # Parse from config
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
    
    # Parse from metrics
    if metrics and isinstance(metrics, dict):
        _parse_metrics(parsed, metrics)
    
    # Parse from status HTML
    if status and isinstance(status, dict) and "raw" in status:
        _parse_status(parsed, status["raw"])
    
    return parsed

def _parse_metrics(parsed, metrics):
    """Parse Prometheus metrics."""
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

def _parse_status(parsed, raw):
    """Parse HTML status page."""
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
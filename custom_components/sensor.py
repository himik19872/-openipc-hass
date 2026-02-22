"""Sensor platform for OpenIPC."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import (
    UnitOfTemperature, 
    UnitOfTime,
    PERCENTAGE,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for sensor_type, sensor_config in SENSOR_TYPES.items():
        entities.append(
            OpenIPCSensor(coordinator, entry, sensor_type, sensor_config)
        )
    
    async_add_entities(entities)

class OpenIPCSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OpenIPC sensor."""

    def __init__(self, coordinator, entry, sensor_type, sensor_config):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.sensor_type = sensor_type
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {sensor_config['name']}"
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_native_unit_of_measurement = sensor_config.get("unit")
        self._attr_icon = sensor_config["icon"]
        
        # Устанавливаем правильные device class
        if sensor_type == "cpu_temp":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif sensor_type == "uptime":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        elif sensor_type == "uptime_seconds":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.SECONDS
        elif sensor_type in ["mem_total", "mem_free", "mem_available", "sd_free", "sd_total", "sd_used"]:
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = "MB"
        elif sensor_type in ["network_rx_bytes", "network_tx_bytes"]:
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = "B"
        elif sensor_type in ["http_requests", "jpeg_requests"]:
            self._attr_state_class = "total_increasing"
        elif sensor_type in ["fps", "isp_fps"]:
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = "fps"
        elif sensor_type == "bitrate":
            self._attr_native_unit_of_measurement = "kbps"
        elif sensor_type == "wifi_signal":
            # Для WiFi сигнала используем проценты без device class
            self._attr_device_class = None
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif sensor_type == "motion_sensitivity":
            self._attr_native_unit_of_measurement = ""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data.get("available", False):
            return None
            
        parsed = self.coordinator.data.get("parsed", {})
        
        _LOGGER.debug("Sensor %s raw value: %s", self.sensor_type, parsed.get(self.sensor_type))
        
        if self.sensor_type == "uptime":
            value = parsed.get("uptime_seconds", 0)
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
            
        elif self.sensor_type == "uptime_seconds":
            value = parsed.get("uptime_seconds", 0)
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
            
        elif self.sensor_type == "cpu_temp":
            value = parsed.get("cpu_temp", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "sd_free":
            value = parsed.get("sd_free", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
            
        elif self.sensor_type == "sd_total":
            value = parsed.get("sd_total", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
            
        elif self.sensor_type == "sd_used":
            value = parsed.get("sd_used", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
            
        elif self.sensor_type == "wifi_signal":
            value = parsed.get("wifi_signal", 0)
            try:
                # Проценты от 0 до 100
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "fps":
            value = parsed.get("fps", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "isp_fps":
            value = parsed.get("isp_fps", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "bitrate":
            value = parsed.get("bitrate", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "resolution":
            return parsed.get("resolution", "unknown")
            
        elif self.sensor_type == "audio_codec":
            return parsed.get("audio_codec", "unknown")
            
        elif self.sensor_type == "motion_sensitivity":
            value = parsed.get("motion_sensitivity", 0)
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "mem_total":
            value = parsed.get("mem_total", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "mem_free":
            value = parsed.get("mem_free", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "mem_available":
            value = parsed.get("mem_available", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "network_rx_bytes":
            value = parsed.get("network_rx_bytes", 0)
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "network_tx_bytes":
            value = parsed.get("network_tx_bytes", 0)
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "http_requests":
            value = parsed.get("http_requests", 0)
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "jpeg_requests":
            value = parsed.get("jpeg_requests", 0)
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "majestic_cpu_user":
            value = parsed.get("majestic_cpu_user", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "majestic_cpu_system":
            value = parsed.get("majestic_cpu_system", 0)
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
                
        elif self.sensor_type == "hostname":
            return parsed.get("hostname", "unknown")
            
        elif self.sensor_type == "architecture":
            return parsed.get("architecture", "unknown")
            
        elif self.sensor_type == "kernel":
            return parsed.get("kernel", "unknown")
        
        return None

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
            "hw_version": parsed.get("architecture", "Unknown"),
        }
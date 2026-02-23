"""Sensor platform for OpenIPC integration."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.const import (
    UnitOfTemperature, 
    UnitOfTime,
    PERCENTAGE,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, 
    SENSOR_TYPES,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_BEWARD,
    DEVICE_TYPE_VIVOTEK,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE, "openipc")
    
    entities = []
    
    # Стандартные сенсоры OpenIPC
    for sensor_type, sensor_config in SENSOR_TYPES.items():
        entities.append(
            OpenIPCSensor(coordinator, entry, sensor_type, sensor_config)
        )
    
    # Специфичные сенсоры для Beward
    if device_type == DEVICE_TYPE_BEWARD and coordinator.beward:
        entities.extend([
            BewardStatusSensor(coordinator, entry),
            BewardDoorSensor(coordinator, entry),
            BewardMotionSensor(coordinator, entry),
            BewardSoundSensor(coordinator, entry),
            BewardTemperatureSensor(coordinator, entry),
            BewardLastEventSensor(coordinator, entry),
        ])
        _LOGGER.info("✅ Added Beward-specific sensors for %s", entry.data.get('name'))
    
    # Специфичные сенсоры для Vivotek
    elif device_type == DEVICE_TYPE_VIVOTEK and coordinator.vivotek:
        entities.extend([
            VivotekStatusSensor(coordinator, entry),
            VivotekTamperSensor(coordinator, entry),
            VivotekDioSensor(coordinator, entry),
            VivotekTemperatureSensor(coordinator, entry),
        ])
        _LOGGER.info("✅ Added Vivotek-specific sensors for %s", entry.data.get('name'))
    
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


# ==================== Beward Specific Sensors ====================

class BewardStatusSensor(CoordinatorEntity, SensorEntity):
    """Beward doorbell status sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Status"
        self._attr_unique_id = f"{entry.entry_id}_beward_status"
        self._attr_icon = "mdi:doorbell"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.beward:
            return "online" if self.coordinator.beward.is_available else "offline"
        return "unknown"

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        if not self.coordinator.beward:
            return {}
        
        return {
            "host": self.coordinator.beward.host,
            "camera_name": self.coordinator.beward.camera_name,
            "model_type": self.coordinator.beward.model_type,
            "last_motion": self.coordinator.beward.state.get("last_motion"),
            "last_sensor": self.coordinator.beward.state.get("last_sensor"),
            "last_sound": self.coordinator.beward.state.get("last_sound"),
        }

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "Doorbell",
        }


class BewardDoorSensor(CoordinatorEntity, BinarySensorEntity):
    """Beward door sensor (open/closed)."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Door"
        self._attr_unique_id = f"{entry.entry_id}_beward_door"
        self._attr_icon = "mdi:door"
        self._attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self):
        """Return true if door is open."""
        if self.coordinator.beward:
            return self.coordinator.beward.state.get("door", False)
        return False


class BewardMotionSensor(CoordinatorEntity, BinarySensorEntity):
    """Beward motion sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Motion"
        self._attr_unique_id = f"{entry.entry_id}_beward_motion"
        self._attr_icon = "mdi:motion-sensor"
        self._attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def is_on(self):
        """Return true if motion detected."""
        if self.coordinator.beward:
            return self.coordinator.beward.state.get("motion", False)
        return False


class BewardSoundSensor(CoordinatorEntity, BinarySensorEntity):
    """Beward sound sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Sound"
        self._attr_unique_id = f"{entry.entry_id}_beward_sound"
        self._attr_icon = "mdi:ear-hearing"
        self._attr_device_class = BinarySensorDeviceClass.SOUND

    @property
    def is_on(self):
        """Return true if sound detected."""
        if self.coordinator.beward:
            return self.coordinator.beward.state.get("sound", False)
        return False


class BewardTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Beward temperature sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Temperature"
        self._attr_unique_id = f"{entry.entry_id}_beward_temperature"
        self._attr_icon = "mdi:thermometer"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Return the temperature."""
        if self.coordinator.beward:
            return self.coordinator.beward.state.get("temperature")
        return None


class BewardLastEventSensor(CoordinatorEntity, SensorEntity):
    """Beward last event sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Last Event"
        self._attr_unique_id = f"{entry.entry_id}_beward_last_event"
        self._attr_icon = "mdi:history"

    @property
    def native_value(self):
        """Return the last event."""
        if not self.coordinator.beward:
            return "unknown"
        
        # Определяем последнее событие
        events = []
        if self.coordinator.beward.state.get("motion", False):
            events.append("motion")
        if self.coordinator.beward.state.get("door", False):
            events.append("door")
        if self.coordinator.beward.state.get("sound", False):
            events.append("sound")
        
        return ", ".join(events) if events else "none"


# ==================== Vivotek Specific Sensors ====================

class VivotekStatusSensor(CoordinatorEntity, SensorEntity):
    """Vivotek camera status sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Vivotek')} Status"
        self._attr_unique_id = f"{entry.entry_id}_vivotek_status"
        self._attr_icon = "mdi:camera"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.vivotek:
            return "online" if self.coordinator.vivotek.is_available else "offline"
        return "unknown"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Vivotek Camera"),
            "manufacturer": "Vivotek",
            "model": "PTZ Camera",
        }


class VivotekTamperSensor(CoordinatorEntity, BinarySensorEntity):
    """Vivotek tamper detection sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Vivotek')} Tamper"
        self._attr_unique_id = f"{entry.entry_id}_vivotek_tamper"
        self._attr_icon = "mdi:alert"
        self._attr_device_class = BinarySensorDeviceClass.TAMPER

    @property
    def is_on(self):
        """Return true if tamper detected."""
        # Здесь нужно добавить логику получения статуса Tamper
        return False


class VivotekDioSensor(CoordinatorEntity, BinarySensorEntity):
    """Vivotek DIO (digital input) sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Vivotek')} Digital Input"
        self._attr_unique_id = f"{entry.entry_id}_vivotek_dio"
        self._attr_icon = "mdi:digital-input"

    @property
    def is_on(self):
        """Return true if digital input is active."""
        # Здесь нужно добавить логику получения состояния DIO
        return False


class VivotekTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Vivotek temperature sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Vivotek')} Temperature"
        self._attr_unique_id = f"{entry.entry_id}_vivotek_temperature"
        self._attr_icon = "mdi:thermometer"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Return the temperature."""
        # Здесь нужно добавить логику получения температуры
        return None
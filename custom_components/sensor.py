"""Sensor platform for OpenIPC integration."""
import logging
import asyncio
from datetime import datetime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.const import (
    UnitOfTemperature, 
    UnitOfTime,
    PERCENTAGE,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
import aiohttp

from .const import (
    DOMAIN, 
    SENSOR_TYPES,
    BINARY_SENSOR_TYPES,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_BEWARD,
    DEVICE_TYPE_VIVOTEK,
    DEVICE_TYPE_OPENIPC,
    LNPR_STATE,
    LNPR_LIST,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE, "openipc")
    
    entities = []
    
    # Стандартные сенсоры OpenIPC
    for sensor_type, sensor_config in SENSOR_TYPES.items():
        # Пропускаем LNPR сенсоры для не-Beward устройств
        if sensor_type.startswith("lnpr_") and device_type != DEVICE_TYPE_BEWARD:
            continue
        entities.append(
            OpenIPCSensor(coordinator, entry, sensor_type, sensor_config)
        )
    
    # Специфичные сенсоры для Beward
    if device_type == DEVICE_TYPE_BEWARD and coordinator.beward:
        _LOGGER.info(f"🔧 Setting up Beward sensors for {entry.data.get('name')}")
        
        beward_sensors = [
            BewardStatusSensor(coordinator, entry),
            BewardDoorSensor(coordinator, entry),
            BewardMotionSensor(coordinator, entry),
            BewardBreakInSensor(coordinator, entry),
            BewardNetworkSensor(coordinator, entry),
            BewardTemperatureSensor(coordinator, entry),
            BewardLastEventSensor(coordinator, entry),
            BewardAudioSensor(coordinator, entry),
            # Новый сенсор для отслеживания конкретных номеров
            BewardPlateTrackerSensor(coordinator, entry),
        ]
        
        entities.extend(beward_sensors)
        _LOGGER.info(f"✅ Added {len(beward_sensors)} Beward-specific sensors for {entry.data.get('name')}")
    
    # Специфичные сенсоры для Vivotek
    elif device_type == DEVICE_TYPE_VIVOTEK and coordinator.vivotek:
        _LOGGER.info(f"🔧 Setting up Vivotek sensors for {entry.data.get('name')}")
        
        vivotek_sensors = [
            VivotekStatusSensor(coordinator, entry),
            VivotekTamperSensor(coordinator, entry),
            VivotekDioSensor(coordinator, entry),
            VivotekTemperatureSensor(coordinator, entry),
        ]
        
        entities.extend(vivotek_sensors)
        _LOGGER.info(f"✅ Added {len(vivotek_sensors)} Vivotek-specific sensors for {entry.data.get('name')}")
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info(f"✅ Total {len(entities)} sensors added for {entry.data.get('name')}")


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
        
        # Для LNPR сенсоров - принудительно строковой тип
        if sensor_type.startswith("lnpr_"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_device_class = None
            # Для строковых сенсоров unit должен быть None
            if sensor_type in ["lnpr_last_number", "lnpr_last_direction", "lnpr_last_time"]:
                self._attr_native_unit_of_measurement = None
            # Убираем state_class для строковых сенсоров
            self._attr_state_class = None
        
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
        
        # Для LNPR сенсоров - возвращаем строки, а не числа!
        if self.sensor_type == "lnpr_last_number":
            lnpr_data = self.coordinator.data.get("lnpr", {})
            value = lnpr_data.get("last_number", "none")
            return str(value)  # Принудительно строка
        elif self.sensor_type == "lnpr_last_direction":
            lnpr_data = self.coordinator.data.get("lnpr", {})
            value = lnpr_data.get("last_direction", "unknown")
            return str(value)  # Принудительно строка
        elif self.sensor_type == "lnpr_last_time":
            lnpr_data = self.coordinator.data.get("lnpr", {})
            value = lnpr_data.get("last_time", "none")
            return str(value)  # Принудительно строка
        elif self.sensor_type == "lnpr_total_today":
            lnpr_data = self.coordinator.data.get("lnpr", {})
            return lnpr_data.get("total_today", 0)
        elif self.sensor_type == "lnpr_authorized_count":
            lnpr_data = self.coordinator.data.get("lnpr", {})
            return lnpr_data.get("authorized_count", 0)
        
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
    def extra_state_attributes(self):
        """Return additional attributes."""
        attrs = {}
        
        # Добавляем LNPR атрибуты для соответствующего сенсора
        if self.sensor_type.startswith("lnpr_"):
            lnpr_data = self.coordinator.data.get("lnpr", {})
            attrs["last_number"] = lnpr_data.get("last_number", "none")
            attrs["last_direction"] = lnpr_data.get("last_direction", "unknown")
            attrs["last_time"] = lnpr_data.get("last_time", "none")
            attrs["coordinates"] = lnpr_data.get("last_coordinates", "")
            attrs["size"] = lnpr_data.get("last_size", "")
            
            if self.sensor_type == "lnpr_last_number":
                attrs["authorized"] = lnpr_data.get("last_authorized", False)
        
        return attrs

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
        self._attr_device_class = None  # Строковой сенсор

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
        
        attrs = {
            "host": self.coordinator.beward.host,
            "camera_name": self.coordinator.beward.camera_name,
            "model": getattr(self.coordinator.beward, '_model', 'DS07P-LP'),
            "audio_enabled": self.coordinator.beward.audio_config.get("audio_switch") == "open",
            "audio_type": self.coordinator.beward.audio_config.get("audio_type"),
            "volume": self.coordinator.beward.state.get("volume", 50),
            "lnpr_enabled": self.coordinator.data.get("lnpr", {}).get("enabled", False),
        }
        
        # Добавляем поля из state если они есть
        if hasattr(self.coordinator.beward, 'state'):
            state = self.coordinator.beward.state
            if "last_motion" in state:
                attrs["last_motion"] = state["last_motion"]
            if "last_door_open" in state:
                attrs["last_door_open"] = state["last_door_open"]
            if "last_break_in" in state:
                attrs["last_break_in"] = state["last_break_in"]
        
        return attrs

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


class BewardDoorSensor(CoordinatorEntity, BinarySensorEntity):
    """Beward door sensor (open/closed) - использует door_open."""

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
            return self.coordinator.beward.door_open
        return False


class BewardMotionSensor(CoordinatorEntity, BinarySensorEntity):
    """Beward motion sensor - использует motion_detected."""

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
            return self.coordinator.beward.motion_detected
        return False


class BewardBreakInSensor(CoordinatorEntity, BinarySensorEntity):
    """Beward break-in detection sensor - использует break_in_detected."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Break In"
        self._attr_unique_id = f"{entry.entry_id}_beward_break_in"
        self._attr_icon = "mdi:alert"
        self._attr_device_class = BinarySensorDeviceClass.TAMPER

    @property
    def is_on(self):
        """Return true if break-in detected."""
        if self.coordinator.beward:
            return self.coordinator.beward.break_in_detected
        return False


class BewardNetworkSensor(CoordinatorEntity, BinarySensorEntity):
    """Beward network status sensor - использует network_ok."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Network"
        self._attr_unique_id = f"{entry.entry_id}_beward_network"
        self._attr_icon = "mdi:wifi"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self):
        """Return true if network is OK."""
        if self.coordinator.beward:
            return self.coordinator.beward.network_ok
        return True


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
        self._attr_device_class = None  # Строковой сенсор

    @property
    def native_value(self):
        """Return the last event."""
        if not self.coordinator.beward:
            return "unknown"
        
        events = []
        if self.coordinator.beward.motion_detected:
            events.append("motion")
        if self.coordinator.beward.door_open:
            events.append("door_open")
        if self.coordinator.beward.break_in_detected:
            events.append("break_in")
        if not self.coordinator.beward.network_ok:
            events.append("network_down")
        
        # Добавляем LNPR события
        lnpr_data = self.coordinator.data.get("lnpr", {})
        if lnpr_data.get("last_number") and lnpr_data["last_number"] != "none":
            events.append(f"plate_{lnpr_data['last_number']}")
        
        return ", ".join(events) if events else "none"


class BewardAudioSensor(CoordinatorEntity, SensorEntity):
    """Beward audio status sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Audio"
        self._attr_unique_id = f"{entry.entry_id}_beward_audio"
        self._attr_icon = "mdi:speaker"
        self._attr_device_class = None  # Строковой сенсор

    @property
    def native_value(self):
        """Return audio status."""
        if not self.coordinator.beward:
            return "unknown"
        
        if self.coordinator.beward.audio_config.get("audio_switch") == "open":
            return "enabled"
        return "disabled"

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        if not self.coordinator.beward:
            return {}
        
        return {
            "volume": self.coordinator.beward.state.get("volume", 50),
            "audio_type": self.coordinator.beward.audio_config.get("audio_type"),
            "echo_cancellation": self.coordinator.beward.audio_config.get("echo_cancellation"),
            "audio_in_vol": self.coordinator.beward.audio_config.get("audio_in_vol"),
            "audio_out_vol": self.coordinator.beward.audio_config.get("audio_out_vol"),
        }


# ==================== Beward Plate Tracker Sensor ====================

class BewardPlateTrackerSensor(CoordinatorEntity, SensorEntity):
    """
    Сенсор для отслеживания конкретных номеров.
    Позволяет в автоматизациях проверять, какой номер въехал или выехал.
    """
    
    # Словарь для хранения состояния по каждому отслеживаемому номеру
    _plates_state = {}

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Plate Tracker"
        self._attr_unique_id = f"{entry.entry_id}_plate_tracker"
        self._attr_icon = "mdi:car-multiple"
        self._attr_device_class = None  # Строковой сенсор
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
        # Инициализируем состояние для этого экземпляра
        self._plate_states = {}

    @property
    def native_value(self):
        """
        Возвращает последний распознанный номер.
        Используйте этот сенсор в автоматизациях для проверки конкретного номера.
        """
        lnpr_data = self.coordinator.data.get("lnpr", {})
        last_number = lnpr_data.get("last_number", "none")
        last_direction = lnpr_data.get("last_direction", "unknown")
        
        # Обновляем состояние для этого номера
        if last_number != "none":
            # Обновляем время последнего появления
            current_time = datetime.now().isoformat()
            
            # Сохраняем в общем словаре
            if last_number not in self._plates_state:
                self._plates_state[last_number] = {
                    "first_seen": current_time,
                    "last_seen": current_time,
                    "direction": last_direction,
                    "count": 1
                }
            else:
                self._plates_state[last_number]["last_seen"] = current_time
                self._plates_state[last_number]["direction"] = last_direction
                self._plates_state[last_number]["count"] += 1
            
            # Сохраняем в локальном словаре для этого экземпляра
            self._plate_states = self._plates_state.copy()
        
        return last_number

    @property
    def extra_state_attributes(self):
        """Return additional attributes with all tracked plates."""
        attrs = {
            "last_plate": self.native_value,
            "last_direction": self.coordinator.data.get("lnpr", {}).get("last_direction", "unknown"),
            "last_time": self.coordinator.data.get("lnpr", {}).get("last_time", "none"),
            "tracked_plates": self._plate_states,
            "plates_count": len(self._plate_states),
        }
        
        # Добавляем атрибуты для каждого конкретного номера для удобства в автоматизациях
        for plate, data in self._plate_states.items():
            # Создаем атрибуты вида: plate_A123BC77_seen, plate_A123BC77_direction и т.д.
            safe_plate = plate.replace(' ', '_').replace('-', '_').replace('*', '_')
            attrs[f"plate_{safe_plate}_seen"] = data["last_seen"]
            attrs[f"plate_{safe_plate}_direction"] = data["direction"]
            attrs[f"plate_{safe_plate}_count"] = data["count"]
        
        return attrs

    def get_plate_info(self, plate_number: str) -> dict:
        """
        Получить информацию о конкретном номере.
        Можно использовать в шаблонах автоматизаций.
        """
        return self._plate_states.get(plate_number, {})

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


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
        self._attr_device_class = None  # Строковой сенсор

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.vivotek:
            return "online" if self.coordinator.vivotek.is_available else "offline"
        return "unknown"

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        if not self.coordinator.vivotek:
            return {}
        
        return {
            "host": self.coordinator.vivotek.host,
            "camera_name": self.coordinator.vivotek.camera_name,
            "model": self.coordinator.vivotek.model_name,
            "firmware": self.coordinator.vivotek.firmware_version,
            "serial": self.coordinator.vivotek.serial_number,
            "rtsp_port": self.coordinator.vivotek.rtsp_port,
            "http_port": self.coordinator.vivotek.http_port,
        }

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Vivotek Camera"),
            "manufacturer": "Vivotek",
            "model": "SD9364-EHL",
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
        return None
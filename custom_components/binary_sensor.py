"""Binary sensor platform for OpenIPC."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, BINARY_SENSOR_TYPES, DEVICE_TYPE_BEWARD

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get("device_type", "openipc")
    
    entities = []
    
    # Стандартные бинарные сенсоры
    for sensor_type, sensor_config in BINARY_SENSOR_TYPES.items():
        # Пропускаем LNPR сенсоры для не-Beward устройств
        if sensor_type.startswith("lnpr_") and device_type != DEVICE_TYPE_BEWARD:
            continue
        entities.append(
            OpenIPCBinarySensor(coordinator, entry, sensor_type, sensor_config)
        )
    
    # Добавляем специфичные Beward бинарные сенсоры (не LNPR)
    if device_type == DEVICE_TYPE_BEWARD and coordinator.beward:
        # Здесь можно добавить другие Beward-специфичные бинарные сенсоры если нужно
        pass
    
    async_add_entities(entities)


class OpenIPCBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an OpenIPC binary sensor."""

    def __init__(self, coordinator, entry, sensor_type, sensor_config):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.sensor_type = sensor_type
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {sensor_config['name']}"
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_icon = sensor_config["icon"]
        
        # Для LNPR сенсоров добавляем категорию диагностики
        if sensor_type.startswith("lnpr_"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
        # Устанавливаем правильные device class
        if sensor_type == "online":
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        elif sensor_type == "motion":
            self._attr_device_class = BinarySensorDeviceClass.MOTION
        elif sensor_type == "night_mode":
            self._attr_device_class = BinarySensorDeviceClass.LIGHT
        elif sensor_type == "recording":
            self._attr_device_class = BinarySensorDeviceClass.RUNNING
        elif sensor_type == "audio_enabled":
            self._attr_device_class = BinarySensorDeviceClass.SOUND
        elif sensor_type == "speaker_enabled":
            self._attr_device_class = BinarySensorDeviceClass.SOUND
        elif sensor_type == "lnpr_authorized":
            self._attr_device_class = BinarySensorDeviceClass.LOCK
        elif sensor_type == "lnpr_unauthorized":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # Проверяем доступность камеры
        if not self.coordinator.data.get("available", False):
            return False
            
        # Стандартные сенсоры
        if self.sensor_type == "online":
            return self.coordinator.data.get("available", False)
            
        elif self.sensor_type == "motion":
            parsed = self.coordinator.data.get("parsed", {})
            return parsed.get("motion_detected", False)
            
        elif self.sensor_type == "recording":
            recording = self.coordinator.data.get("recording", {})
            return recording.get("recording", False)
            
        elif self.sensor_type == "night_mode":
            parsed = self.coordinator.data.get("parsed", {})
            # Проверяем несколько возможных источников
            night_mode = parsed.get("night_mode_enabled", False)
            night_mode_metrics = parsed.get("night_mode_enabled_metrics", False)
            return night_mode or night_mode_metrics
            
        elif self.sensor_type == "ircut":
            parsed = self.coordinator.data.get("parsed", {})
            return parsed.get("ircut_enabled_metrics", False)
            
        elif self.sensor_type == "night_light":
            parsed = self.coordinator.data.get("parsed", {})
            return parsed.get("light_enabled_metrics", False)
            
        elif self.sensor_type == "audio_enabled":
            parsed = self.coordinator.data.get("parsed", {})
            return parsed.get("audio_enabled", False)
            
        elif self.sensor_type == "speaker_enabled":
            parsed = self.coordinator.data.get("parsed", {})
            return parsed.get("speaker_enabled", False)
            
        # LNPR сенсоры
        elif self.sensor_type.startswith("lnpr_"):
            lnpr_data = self.coordinator.data.get("lnpr", {})
            
            if self.sensor_type == "lnpr_authorized":
                return lnpr_data.get("last_authorized", False)
                
            elif self.sensor_type == "lnpr_unauthorized":
                # Сенсор активен когда есть номер, но он не авторизован
                return (lnpr_data.get("last_number") and 
                        lnpr_data.get("last_number") != "none" and
                        not lnpr_data.get("last_authorized", False))
        
        return False

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        attrs = {}
        
        # Добавляем атрибуты для LNPR сенсоров
        if self.sensor_type.startswith("lnpr_"):
            lnpr_data = self.coordinator.data.get("lnpr", {})
            
            # Основные атрибуты
            attrs["last_number"] = lnpr_data.get("last_number", "none")
            attrs["last_direction"] = lnpr_data.get("last_direction", "unknown")
            attrs["last_time"] = lnpr_data.get("last_time", "none")
            
            # Дополнительные атрибуты если есть
            if lnpr_data.get("last_coordinates"):
                attrs["coordinates"] = lnpr_data["last_coordinates"]
            if lnpr_data.get("last_size"):
                attrs["size"] = lnpr_data["last_size"]
            
            # Для неавторизованных добавляем предупреждение
            if self.sensor_type == "lnpr_unauthorized" and self.is_on:
                attrs["alert"] = "⚠️ Unknown vehicle detected!"
        
        # Добавляем атрибуты для сенсора online
        elif self.sensor_type == "online":
            attrs["last_update"] = self.coordinator.data.get("last_update")
        
        return attrs

    @property
    def device_info(self):
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {})
        
        # Определяем производителя в зависимости от типа устройства
        if self.entry.data.get("device_type") == DEVICE_TYPE_BEWARD:
            manufacturer = "Beward"
            model = "DS07P-LP"
        else:
            manufacturer = "OpenIPC"
            model = parsed.get("model", "Camera")
        
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "OpenIPC Camera"),
            "manufacturer": manufacturer,
            "model": model,
            "sw_version": parsed.get("firmware", "Unknown"),
            "hw_version": parsed.get("architecture", "Unknown"),
        }
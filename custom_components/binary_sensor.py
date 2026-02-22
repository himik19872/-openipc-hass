"""Binary sensor platform for OpenIPC."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BINARY_SENSOR_TYPES

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for sensor_type, sensor_config in BINARY_SENSOR_TYPES.items():
        entities.append(
            OpenIPCBinarySensor(coordinator, entry, sensor_type, sensor_config)
        )
    
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
        
        if sensor_type == "online":
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        elif sensor_type == "motion":
            self._attr_device_class = BinarySensorDeviceClass.MOTION
        elif sensor_type == "night_mode":
            self._attr_device_class = BinarySensorDeviceClass.LIGHT

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self.sensor_type == "online":
            return self.coordinator.data.get("available", False)
        elif self.sensor_type == "motion":
            parsed = self.coordinator.data.get("parsed", {})
            return parsed.get("motion_detected", False)
        elif self.sensor_type == "night_mode":
            # Можно добавить логику для определения ночного режима
            return False
        elif self.sensor_type == "recording":
            # Можно добавить логику для определения записи
            return False
        return False

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
        }
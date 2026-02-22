"""Select platform for OpenIPC (recording duration)."""
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Варианты длительности записи (в секундах)
RECORDING_DURATIONS = {
    "15 seconds": 15,
    "30 seconds": 30,
    "1 minute": 60,
    "2 minutes": 120,
    "3 minutes": 180,
    "5 minutes": 300,
    "10 minutes": 600,
    "15 minutes": 900,
    "30 minutes": 1800,
    "1 hour": 3600,
}

# Опции для select
RECORDING_OPTIONS = list(RECORDING_DURATIONS.keys())

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        OpenIPCRecordingDurationSelect(coordinator, entry),
    ]
    
    async_add_entities(entities)

class OpenIPCRecordingDurationSelect(CoordinatorEntity, SelectEntity, RestoreEntity):
    """Representation of a recording duration select entity."""

    def __init__(self, coordinator, entry):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} Recording Duration"
        self._attr_unique_id = f"{entry.entry_id}_recording_duration"
        self._attr_icon = "mdi:timer"
        self._attr_options = RECORDING_OPTIONS
        self._attr_current_option = "1 minute"  # Значение по умолчанию

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        
        # Восстанавливаем предыдущее состояние
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored recording duration: %s", self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()
            
            duration = RECORDING_DURATIONS[option]
            _LOGGER.info("Recording duration set to %s (%d seconds)", option, duration)
            
            # Сохраняем в coordinator для использования другими компонентами
            self.coordinator.recording_duration = duration

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self._attr_current_option

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
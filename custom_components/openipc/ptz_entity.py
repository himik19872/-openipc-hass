"""PTZ entities for camera control."""
import logging
from typing import Optional

from homeassistant.components.select import SelectEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up PTZ entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    if not hasattr(coordinator, 'onvif') or not coordinator.onvif:
        _LOGGER.debug("ONVIF not configured")
        return
    
    entities = []
    
    # PTZ speed control
    entities.append(OpenIPCPtzSpeedNumber(coordinator, entry))
    
    # PTZ presets select
    if coordinator.onvif.has_ptz:
        entities.append(OpenIPCPresetSelect(coordinator, entry))
        entities.append(OpenIPCPresetSetButton(coordinator, entry))
        entities.append(OpenIPCPresetRefreshButton(coordinator, entry))
    
    async_add_entities(entities)

class OpenIPCPtzSpeedNumber(CoordinatorEntity, NumberEntity):
    """PTZ movement speed control."""

    def __init__(self, coordinator, entry):
        """Initialize the number."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} PTZ Speed"
        self._attr_unique_id = f"{entry.entry_id}_ptz_speed"
        self._attr_icon = "mdi:speedometer"
        self._attr_native_min_value = 0.1
        self._attr_native_max_value = 1.0
        self._attr_native_step = 0.1
        self._attr_native_unit_of_measurement = ""
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float:
        """Return current speed."""
        if self.coordinator.onvif:
            return self.coordinator.onvif.ptz_speed
        return 0.5

    async def async_set_native_value(self, value: float) -> None:
        """Set new speed."""
        if self.coordinator.onvif:
            self.coordinator.onvif.ptz_speed = value
            self.async_write_ha_state()

class OpenIPCPresetSelect(CoordinatorEntity, SelectEntity):
    """PTZ presets selector."""

    def __init__(self, coordinator, entry):
        """Initialize the select."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} PTZ Preset"
        self._attr_unique_id = f"{entry.entry_id}_ptz_preset"
        self._attr_icon = "mdi:map-marker"

    @property
    def options(self) -> list[str]:
        """Return available presets."""
        if self.coordinator.onvif:
            return list(self.coordinator.onvif.presets.keys())
        return []

    @property
    def current_option(self) -> Optional[str]:
        """Return current preset."""
        return None  # No current preset indicator

    async def async_select_option(self, option: str) -> None:
        """Go to selected preset."""
        if self.coordinator.onvif:
            preset_token = self.coordinator.onvif.presets.get(option)
            if preset_token:
                await self.coordinator.onvif.async_ptz_goto_preset(preset_token)

class OpenIPCPresetSetButton(CoordinatorEntity, ButtonEntity):
    """Button to set current position as preset."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} Set Preset"
        self._attr_unique_id = f"{entry.entry_id}_ptz_set_preset"
        self._attr_icon = "mdi:map-marker-plus"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle button press."""
        if self.coordinator.onvif:
            # В реальном коде можно добавить поле ввода имени через action
            await self.coordinator.onvif.async_ptz_set_preset(f"Preset_{len(self.coordinator.onvif.presets) + 1}")

class OpenIPCPresetRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to refresh presets list."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} Refresh Presets"
        self._attr_unique_id = f"{entry.entry_id}_ptz_refresh"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle button press."""
        if self.coordinator.onvif:
            await self.coordinator.onvif.async_update_presets()
            # Принудительно обновляем состояние select
            self.async_write_ha_state()
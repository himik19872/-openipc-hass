"""PTZ entities for Vivotek camera."""
import logging
from typing import Optional, List

from homeassistant.components.select import SelectEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_ptz_entities(hass, entry, async_add_entities, coordinator):
    """Set up PTZ entities."""
    if not coordinator.vivotek or not coordinator.vivotek.ptz_available:
        _LOGGER.warning("PTZ not available for this Vivotek camera")
        return
    
    entities = []
    
    # Кнопки движения
    movements = [
        ("up", "Up", "mdi:arrow-up"),
        ("down", "Down", "mdi:arrow-down"),
        ("left", "Left", "mdi:arrow-left"),
        ("right", "Right", "mdi:arrow-right"),
        ("up-left", "Up-Left", "mdi:arrow-top-left"),
        ("up-right", "Up-Right", "mdi:arrow-top-right"),
        ("down-left", "Down-Left", "mdi:arrow-bottom-left"),
        ("down-right", "Down-Right", "mdi:arrow-bottom-right"),
    ]
    
    for direction, name, icon in movements:
        entities.append(
            VivotekPTZMoveButton(coordinator, entry, direction, name, icon)
        )
    
    # Кнопки управления
    entities.extend([
        VivotekPTZStopButton(coordinator, entry),
        VivotekPTZHomeButton(coordinator, entry),
        VivotekPTZZoomInButton(coordinator, entry),
        VivotekPTZZoomOutButton(coordinator, entry),
    ])
    
    # Управление скоростью
    entities.append(VivotekPTZSpeedNumber(coordinator, entry))
    
    # Пресеты
    entities.append(VivotekPTZPresetSelect(coordinator, entry))
    entities.append(VivotekPTZSetPresetButton(coordinator, entry))
    entities.append(VivotekPTZRefreshPresetsButton(coordinator, entry))
    
    async_add_entities(entities)
    _LOGGER.info(f"✅ Added {len(entities)} PTZ entities for Vivotek")


class VivotekPTZMoveButton(CoordinatorEntity, ButtonEntity):
    """Button for PTZ movement."""

    def __init__(self, coordinator, entry, direction, name, icon):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.direction = direction
        self._attr_name = f"{entry.data.get('name')} PTZ {name}"
        self._attr_unique_id = f"{entry.entry_id}_ptz_{direction}"
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle button press."""
        if not self.coordinator.vivotek or not self.coordinator.vivotek.ptz:
            _LOGGER.error("PTZ not available")
            return
        await self.coordinator.vivotek.ptz.async_move(self.direction, 50)


class VivotekPTZStopButton(CoordinatorEntity, ButtonEntity):
    """Button to stop PTZ movement."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} PTZ Stop"
        self._attr_unique_id = f"{entry.entry_id}_ptz_stop"
        self._attr_icon = "mdi:stop"

    async def async_press(self) -> None:
        """Handle button press."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            await self.coordinator.vivotek.ptz.async_stop()


class VivotekPTZHomeButton(CoordinatorEntity, ButtonEntity):
    """Button to go to home position."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} PTZ Home"
        self._attr_unique_id = f"{entry.entry_id}_ptz_home"
        self._attr_icon = "mdi:home"

    async def async_press(self) -> None:
        """Handle button press."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            await self.coordinator.vivotek.ptz.async_goto_preset(1)


class VivotekPTZZoomInButton(CoordinatorEntity, ButtonEntity):
    """Button for zoom in."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} PTZ Zoom In"
        self._attr_unique_id = f"{entry.entry_id}_ptz_zoom_in"
        self._attr_icon = "mdi:plus"

    async def async_press(self) -> None:
        """Handle button press."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            await self.coordinator.vivotek.ptz.async_move("in", 50)


class VivotekPTZZoomOutButton(CoordinatorEntity, ButtonEntity):
    """Button for zoom out."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} PTZ Zoom Out"
        self._attr_unique_id = f"{entry.entry_id}_ptz_zoom_out"
        self._attr_icon = "mdi:minus"

    async def async_press(self) -> None:
        """Handle button press."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            await self.coordinator.vivotek.ptz.async_move("out", 50)


class VivotekPTZSpeedNumber(CoordinatorEntity, NumberEntity):
    """Number entity for PTZ speed control."""

    def __init__(self, coordinator, entry):
        """Initialize the number."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} PTZ Speed"
        self._attr_unique_id = f"{entry.entry_id}_ptz_speed"
        self._attr_icon = "mdi:speedometer"
        self._attr_native_min_value = 1
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "%"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_value = 50

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = value
        self.async_write_ha_state()


class VivotekPTZPresetSelect(CoordinatorEntity, SelectEntity):
    """Select entity for PTZ presets."""

    def __init__(self, coordinator, entry):
        """Initialize the select."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} PTZ Preset"
        self._attr_unique_id = f"{entry.entry_id}_ptz_preset"
        self._attr_icon = "mdi:map-marker"
        self._presets = {}
        self._attr_options = []

    async def async_added_to_hass(self) -> None:
        """Run when entity added to hass."""
        await self.async_update_presets()

    async def async_update_presets(self):
        """Update presets list."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            self._presets = await self.coordinator.vivotek.ptz.async_get_presets()
            self._attr_options = [
                f"{pid}: {name}" if name else f"Preset {pid}"
                for pid, name in self._presets.items()
            ]
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        if not self.coordinator.vivotek or not self.coordinator.vivotek.ptz:
            return
        try:
            preset_id = int(option.split(':')[0])
            await self.coordinator.vivotek.ptz.async_goto_preset(preset_id)
        except:
            _LOGGER.error("Invalid preset selection: %s", option)


class VivotekPTZSetPresetButton(CoordinatorEntity, ButtonEntity):
    """Button to set current position as preset."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} Set Preset"
        self._attr_unique_id = f"{entry.entry_id}_ptz_set_preset"
        self._attr_icon = "mdi:map-marker-plus"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle button press."""
        if not self.coordinator.vivotek or not self.coordinator.vivotek.ptz:
            return
        
        # Просто устанавливаем пресет 1 для теста
        await self.coordinator.vivotek.ptz._send_command("setpreset", preset=1)


class VivotekPTZRefreshPresetsButton(CoordinatorEntity, ButtonEntity):
    """Button to refresh presets list."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name')} Refresh Presets"
        self._attr_unique_id = f"{entry.entry_id}_ptz_refresh"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle button press."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            await self.coordinator.vivotek.ptz.async_get_presets()
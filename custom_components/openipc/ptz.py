"""PTZ entities for Vivotek camera."""
import logging
from typing import Optional, List

from homeassistant.components.select import SelectEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, DEVICE_TYPE_VIVOTEK

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up PTZ entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    if entry.data.get("device_type") != DEVICE_TYPE_VIVOTEK:
        return
    
    if not coordinator.vivotek or not coordinator.vivotek.ptz_available:
        _LOGGER.warning("PTZ not available for this Vivotek camera")
        return
    
    entities = []
    
    # Кнопки управления
    entities.extend([
        VivotekPTZMoveButton(coordinator, entry, "up", "Up", "mdi:arrow-up"),
        VivotekPTZMoveButton(coordinator, entry, "down", "Down", "mdi:arrow-down"),
        VivotekPTZMoveButton(coordinator, entry, "left", "Left", "mdi:arrow-left"),
        VivotekPTZMoveButton(coordinator, entry, "right", "Right", "mdi:arrow-right"),
        VivotekPTZMoveButton(coordinator, entry, "up-left", "Up-Left", "mdi:arrow-top-left"),
        VivotekPTZMoveButton(coordinator, entry, "up-right", "Up-Right", "mdi:arrow-top-right"),
        VivotekPTZMoveButton(coordinator, entry, "down-left", "Down-Left", "mdi:arrow-bottom-left"),
        VivotekPTZMoveButton(coordinator, entry, "down-right", "Down-Right", "mdi:arrow-bottom-right"),
        VivotekPTZStopButton(coordinator, entry),
        VivotekPTZHomeButton(coordinator, entry),
    ])
    
    # Кнопки зума
    entities.extend([
        VivotekPTZZoomButton(coordinator, entry, "in", "Zoom In", "mdi:plus"),
        VivotekPTZZoomButton(coordinator, entry, "out", "Zoom Out", "mdi:minus"),
    ])
    
    # Управление скоростью
    entities.append(VivotekPTZSpeedNumber(coordinator, entry))
    
    # Пресеты
    entities.append(VivotekPTZPresetSelect(coordinator, entry))
    entities.append(VivotekPTZSetPresetButton(coordinator, entry))
    entities.append(VivotekPTZRefreshPresetsButton(coordinator, entry))
    
    async_add_entities(entities)


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
        
        speed = 50  # Можно сделать настраиваемым
        await self.coordinator.vivotek.ptz.async_move(self.direction, speed)


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
        if not self.coordinator.vivotek or not self.coordinator.vivotek.ptz:
            return
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
        if not self.coordinator.vivotek or not self.coordinator.vivotek.ptz:
            return
        await self.coordinator.vivotek.ptz.async_home()


class VivotekPTZZoomButton(CoordinatorEntity, ButtonEntity):
    """Button for zoom control."""

    def __init__(self, coordinator, entry, direction, name, icon):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.zoom_direction = direction
        self._attr_name = f"{entry.data.get('name')} PTZ {name}"
        self._attr_unique_id = f"{entry.entry_id}_ptz_zoom_{direction}"
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle button press."""
        if not self.coordinator.vivotek or not self.coordinator.vivotek.ptz:
            return
        await self.coordinator.vivotek.ptz.async_zoom(self.zoom_direction, 50)


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

    @property
    def options(self) -> List[str]:
        """Return available presets."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            # Получаем пресеты
            return [f"{pid}: {name}" if name else f"Preset {pid}" 
                   for pid, name in self._presets.items()]
        return []

    async def async_select_option(self, option: str) -> None:
        """Select option."""
        if not self.coordinator.vivotek or not self.coordinator.vivotek.ptz:
            return
        
        # Парсим ID пресета из строки
        try:
            preset_id = int(option.split(':')[0])
            await self.coordinator.vivotek.ptz.async_goto_preset(preset_id)
        except:
            _LOGGER.error("Invalid preset selection: %s", option)

    async def async_update(self) -> None:
        """Update presets."""
        if self.coordinator.vivotek and self.coordinator.vivotek.ptz:
            self._presets = await self.coordinator.vivotek.ptz.async_get_presets()


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
        
        # Находим первый свободный ID пресета
        presets = await self.coordinator.vivotek.ptz.async_get_presets()
        preset_id = 1
        while preset_id in presets:
            preset_id += 1
        
        if preset_id <= 256:
            await self.coordinator.vivotek.ptz.async_set_preset(
                preset_id, f"Preset {preset_id}"
            )
            # Обновляем список пресетов
            await self.coordinator.async_request_refresh()


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
            await self.coordinator.async_request_refresh()
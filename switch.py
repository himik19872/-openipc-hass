"""Switch platform for OpenIPC."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, SWITCH_TYPES, NIGHT_ON, NIGHT_OFF, NIGHT_TOGGLE, NIGHT_IRCUT, NIGHT_LIGHT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for switch_type, switch_config in SWITCH_TYPES.items():
        entities.append(
            OpenIPCSwitch(coordinator, entry, switch_type, switch_config)
        )
    
    async_add_entities(entities)

class OpenIPCSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an OpenIPC switch."""

    def __init__(self, coordinator, entry, switch_type, switch_config):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.switch_type = switch_type
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {switch_config['name']}"
        self._attr_unique_id = f"{entry.entry_id}_{switch_type}"
        self._attr_icon = switch_config["icon"]

    @property
    def is_on(self):
        """Return true if switch is on."""
        parsed = self.coordinator.data.get("parsed", {})
        
        if self.switch_type == "night_mode":
            return parsed.get("night_mode", False)
        elif self.switch_type == "ircut":
            return parsed.get("ircut", False)
        elif self.switch_type == "night_light":
            return parsed.get("night_light", False)
        
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.switch_type == "night_mode":
            await self._send_command(NIGHT_ON)
        elif self.switch_type == "ircut":
            await self._send_command(NIGHT_IRCUT)
        elif self.switch_type == "night_light":
            await self._send_command(NIGHT_LIGHT)
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.switch_type == "night_mode":
            await self._send_command(NIGHT_OFF)
        
        await self.coordinator.async_request_refresh()

    async def _send_command(self, command):
        """Send command to camera."""
        url = f"http://{self.coordinator.host}:{self.coordinator.port}{command}"
        try:
            async with self.coordinator.session.get(url, auth=self.coordinator.auth) as response:
                if response.status == 200:
                    _LOGGER.debug("Command %s sent successfully", command)
                else:
                    _LOGGER.error("Failed to send command %s: HTTP %s", command, response.status)
        except Exception as err:
            _LOGGER.error("Error sending command %s: %s", command, err)

    @property
    def device_info(self):
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {})
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "OpenIPC Camera"),
            "manufacturer": "OpenIPC",
            "model": parsed.get("model", "Camera"),
        }
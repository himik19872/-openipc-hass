"""Switch platform for OpenIPC."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, SWITCH_TYPES, NIGHT_ON, NIGHT_OFF, NIGHT_IRCUT, NIGHT_LIGHT, DEVICE_TYPE_BEWARD

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get("device_type", "openipc")
    
    entities = []
    
    # Стандартные переключатели OpenIPC (ночные режимы и т.д.)
    if device_type != DEVICE_TYPE_BEWARD:
        for switch_type, switch_config in SWITCH_TYPES.items():
            entities.append(
                OpenIPCSwitch(coordinator, entry, switch_type, switch_config)
            )
        _LOGGER.debug(f"Added {len(SWITCH_TYPES)} standard switches for {entry.data.get('name')}")
    
    # Реле для Beward
    if device_type == DEVICE_TYPE_BEWARD and coordinator.beward:
        entities.append(
            BewardRelaySwitch(coordinator, entry, 1, "Main Relay")
        )
        entities.append(
            BewardRelaySwitch(coordinator, entry, 2, "Secondary Relay")
        )
        _LOGGER.info(f"✅ Added Beward relays for {entry.data.get('name')}")
    
    # Реле для OpenIPC (если есть поддержка)
    elif hasattr(coordinator, 'has_relay') and coordinator.has_relay:
        entities.append(
            OpenIPCRelaySwitch(coordinator, entry, 1, "Relay")
        )
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info(f"✅ Total {len(entities)} switches added for {entry.data.get('name')}")


class OpenIPCSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an OpenIPC switch (night mode, IR cut, etc.)."""

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
        if not self.coordinator.data:
            return False
            
        parsed = self.coordinator.data.get("parsed", {})
        
        if self.switch_type == "night_mode":
            return parsed.get("night_mode_enabled", False) or parsed.get("night_mode_enabled_metrics", False)
        elif self.switch_type == "ircut":
            return parsed.get("ircut_enabled_metrics", False)
        elif self.switch_type == "night_light":
            return parsed.get("light_enabled_metrics", False)
        elif self.switch_type == "recording":
            return self.coordinator.data.get("recording", {}).get("recording", False)
        
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.switch_type == "night_mode":
            await self._send_command(NIGHT_ON)
        elif self.switch_type == "ircut":
            await self._send_command(NIGHT_IRCUT)
        elif self.switch_type == "night_light":
            await self._send_command(NIGHT_LIGHT)
        elif self.switch_type == "recording":
            await self.coordinator.async_start_recording()
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.switch_type == "night_mode":
            await self._send_command(NIGHT_OFF)
        elif self.switch_type == "recording":
            await self.coordinator.async_stop_recording()
        
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
        parsed = self.coordinator.data.get("parsed", {}) if self.coordinator.data else {}
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "OpenIPC Camera"),
            "manufacturer": "OpenIPC",
            "model": parsed.get("model", "Camera"),
            "sw_version": parsed.get("firmware", "Unknown"),
        }


class BewardRelaySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Beward relay switch."""

    def __init__(self, coordinator, entry, relay_id: int, name_suffix: str):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.relay_id = relay_id
        self._attr_name = f"{entry.data.get('name', 'Beward')} {name_suffix}"
        self._attr_unique_id = f"{entry.entry_id}_beward_relay_{relay_id}"
        self._attr_icon = "mdi:relay"
        _LOGGER.debug(f"Created Beward relay {relay_id} with unique_id: {self._attr_unique_id}")

    @property
    def is_on(self):
        """Return true if relay is on."""
        if self.coordinator.beward and hasattr(self.coordinator.beward, 'state'):
            state = self.coordinator.beward.state.get(f"relay_{self.relay_id}_state", False)
            _LOGGER.debug(f"Relay {self.relay_id} state: {state}")
            return state
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the relay on."""
        _LOGGER.info(f"🔌 Turning on Beward relay {self.relay_id}")
        if self.coordinator.beward and hasattr(self.coordinator.beward, 'async_set_relay'):
            success = await self.coordinator.beward.async_set_relay(self.relay_id, True)
            _LOGGER.info(f"Relay {self.relay_id} turn on result: {success}")
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the relay off."""
        _LOGGER.info(f"🔌 Turning off Beward relay {self.relay_id}")
        if self.coordinator.beward and hasattr(self.coordinator.beward, 'async_set_relay'):
            success = await self.coordinator.beward.async_set_relay(self.relay_id, False)
            _LOGGER.info(f"Relay {self.relay_id} turn off result: {success}")
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


class OpenIPCRelaySwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an OpenIPC relay switch (for cameras with GPIO relays)."""

    def __init__(self, coordinator, entry, relay_id: int, name_suffix: str):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.relay_id = relay_id
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {name_suffix}"
        self._attr_unique_id = f"{entry.entry_id}_relay_{relay_id}"
        self._attr_icon = "mdi:relay"
        self._state = False

    @property
    def is_on(self):
        """Return true if relay is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the relay on."""
        _LOGGER.info(f"🔌 Turning on OpenIPC relay {self.relay_id}")
        
        endpoints = [
            f"/cgi-bin/relay.cgi?relay={self.relay_id}&state=1",
            f"/cgi-bin/gpio.cgi?pin={self.relay_id}&value=1",
            f"/api/v1/relay/{self.relay_id}/on",
        ]
        
        for endpoint in endpoints:
            try:
                url = f"http://{self.coordinator.host}:{self.coordinator.port}{endpoint}"
                async with self.coordinator.session.get(url, auth=self.coordinator.auth, timeout=3) as response:
                    if response.status == 200:
                        self._state = True
                        self.async_write_ha_state()
                        _LOGGER.info(f"✅ Relay {self.relay_id} turned on via {endpoint}")
                        break
            except Exception as err:
                _LOGGER.debug(f"Failed to turn on relay via {endpoint}: {err}")
                continue
        else:
            _LOGGER.error(f"❌ Failed to turn on relay {self.relay_id} - no working endpoint")
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the relay off."""
        _LOGGER.info(f"🔌 Turning off OpenIPC relay {self.relay_id}")
        
        endpoints = [
            f"/cgi-bin/relay.cgi?relay={self.relay_id}&state=0",
            f"/cgi-bin/gpio.cgi?pin={self.relay_id}&value=0",
            f"/api/v1/relay/{self.relay_id}/off",
        ]
        
        for endpoint in endpoints:
            try:
                url = f"http://{self.coordinator.host}:{self.coordinator.port}{endpoint}"
                async with self.coordinator.session.get(url, auth=self.coordinator.auth, timeout=3) as response:
                    if response.status == 200:
                        self._state = False
                        self.async_write_ha_state()
                        _LOGGER.info(f"✅ Relay {self.relay_id} turned off via {endpoint}")
                        break
            except Exception as err:
                _LOGGER.debug(f"Failed to turn off relay via {endpoint}: {err}")
                continue
        else:
            _LOGGER.error(f"❌ Failed to turn off relay {self.relay_id} - no working endpoint")
        
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {}) if self.coordinator.data else {}
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "OpenIPC Camera"),
            "manufacturer": "OpenIPC",
            "model": parsed.get("model", "Camera"),
            "sw_version": parsed.get("firmware", "Unknown"),
        }
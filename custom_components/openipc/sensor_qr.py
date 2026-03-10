"""QR Scanner sensor for OpenIPC integration."""
import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_IDLE
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo
import aiohttp

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up QR scanner sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Проверяем, есть ли аддон
    if coordinator.use_addon and coordinator.addon.available:
        async_add_entities([QRScannerSensor(coordinator, entry)])

class QRScannerSensor(SensorEntity):
    """QR Scanner sensor for monitoring scan status."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.entry = entry
        self.camera_name = entry.data.get('name', 'OpenIPC')
        self._attr_name = f"{self.camera_name} QR Scanner"
        self._attr_unique_id = f"{entry.entry_id}_qr_scanner"
        self._attr_icon = "mdi:qrcode-scan"
        self._attr_native_value = STATE_IDLE
        self._scan_id = None
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        parsed = self.coordinator.data.get("parsed", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.data.get("name", "OpenIPC Camera"),
            manufacturer="OpenIPC",
            model=parsed.get("model", "Camera"),
            sw_version=parsed.get("firmware", "Unknown"),
        )
    
    async def async_update(self):
        """Update the sensor."""
        if not self._scan_id:
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:5000/api/scan_status/{self._scan_id}"
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        scan = data.get('scan', {})
                        self._attr_native_value = scan.get('status', STATE_IDLE)
                        self._attr_extra_state_attributes = {
                            'start_time': scan.get('start_time'),
                            'expected_code': scan.get('expected_code'),
                            'result': scan.get('result')
                        }
                    else:
                        self._scan_id = None
                        self._attr_native_value = STATE_IDLE
        except:
            self._attr_native_value = STATE_IDLE
    
    def set_scan_id(self, scan_id):
        """Set current scan ID."""
        self._scan_id = scan_id
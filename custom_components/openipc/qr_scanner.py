"""QR Code scanner for OpenIPC cameras with trigger support."""
import logging
import asyncio
import os
import tempfile
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timedelta
from enum import Enum

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change
import aiofiles

from . import qr_utils

_LOGGER = logging.getLogger(__name__)

class QRMode(Enum):
    """QR scanner operation modes."""
    DISABLED = 0
    SINGLE = 1
    PERIODIC = 2
    CONTINUOUS = 3

class QRTrigger:
    """QR scanner trigger configuration."""
    
    def __init__(self, entity_id: str, to_state: str = "on", from_state: str = None):
        self.entity_id = entity_id
        self.to_state = to_state
        self.from_state = from_state
        self.active = False

class QRScanner:
    """QR Code scanner for OpenIPC cameras with trigger support."""

    def __init__(self, hass: HomeAssistant, recorder, camera_entity: str, coordinator=None):
        """Initialize QR scanner."""
        self.hass = hass
        self.recorder = recorder
        self.camera_entity = camera_entity
        self.coordinator = coordinator
        self._mode = QRMode.DISABLED
        self._triggers: List[QRTrigger] = []
        self._scan_interval = 1.0
        self._scan_timeout = 30
        self._scan_task: Optional[asyncio.Task] = None
        self._last_result: Optional[Dict[str, Any]] = None
        self._last_time: Optional[float] = None
        self._active_until: Optional[datetime] = None
        self._active_triggers = set()
        
        # Проверяем доступность библиотек для локального режима
        self._local_available = False
        self._check_libraries_task = None

    async def async_initialize(self):
        """Initialize and check libraries."""
        self._check_libraries_task = asyncio.create_task(self._check_libraries())

    async def _check_libraries(self):
        """Check if local QR libraries are available."""
        self._local_available = await qr_utils.async_check_libraries(self.hass)
        if not self._local_available and not (self.coordinator and self.coordinator.use_addon and self.coordinator.addon.available):
            _LOGGER.warning("QR scanning not available locally and add-on not found")
        elif self._local_available:
            _LOGGER.info("✅ Local QR libraries available")

    @property
    def available(self) -> bool:
        """Return True if QR scanning is available (either local or via add-on)."""
        if self.coordinator and self.coordinator.use_addon and self.coordinator.addon.available:
            return True
        return self._local_available

    async def async_scan_snapshot(self) -> Optional[Dict[str, Any]]:
        """Take a snapshot and scan for QR codes."""
        # Сначала пробуем использовать аддон
        if self.coordinator and self.coordinator.use_addon and self.coordinator.addon.available:
            try:
                _LOGGER.debug("Using add-on for QR scan")
                camera_name = self.recorder.camera_name if hasattr(self.recorder, 'camera_name') else self.camera_entity
                
                snapshot_bytes = await self._capture_snapshot_bytes()
                if not snapshot_bytes:
                    return None
                
                results = await self.coordinator.addon.async_qr_scan(camera_name, timeout=10)
                if results and len(results) > 0:
                    result = results[0]
                    return {
                        "data": result.get("data", ""),
                        "type": result.get("type", "QRCODE"),
                        "rect": result.get("rect", {}),
                        "timestamp": datetime.now().timestamp()
                    }
                return None
            except Exception as err:
                _LOGGER.error(f"Add-on QR scan failed: {err}, falling back to local")
        
        # Fallback на локальный метод
        if not self._local_available:
            return None

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            snapshot_path = tmp.name

        try:
            success = await self._capture_snapshot(snapshot_path)
            if not success:
                return None

            result = await qr_utils.async_scan_image(self.hass, snapshot_path)
            if result:
                result["timestamp"] = datetime.now().timestamp()
            return result

        except Exception as err:
            _LOGGER.error("Error scanning QR code: %s", err)
            return None
        finally:
            if os.path.exists(snapshot_path):
                os.unlink(snapshot_path)

    async def async_scan_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Scan QR code from a file path."""
        _LOGGER.info(f"📁 Scanning QR from file: {file_path}")
        
        if not os.path.exists(file_path):
            _LOGGER.error(f"File not found: {file_path}")
            return None
        
        # Используем аддон если доступен
        if self.coordinator and self.coordinator.use_addon and self.coordinator.addon.available:
            try:
                # Читаем файл
                async with aiofiles.open(file_path, 'rb') as f:
                    image_data = await f.read()
                
                # Кодируем в base64
                import base64
                image_b64 = base64.b64encode(image_data).decode('utf-8')
                
                # Отправляем в аддон
                camera_name = self.recorder.camera_name if hasattr(self.recorder, 'camera_name') else self.camera_entity
                results = await self.coordinator.addon.async_qr_scan(camera_name, timeout=10, image_b64=image_b64)
                
                if results and len(results) > 0:
                    result = results[0]
                    return {
                        "data": result.get("data", ""),
                        "type": result.get("type", "QRCODE"),
                        "rect": result.get("rect", {}),
                        "timestamp": datetime.now().timestamp()
                    }
                return None
                
            except Exception as err:
                _LOGGER.error(f"Add-on QR scan failed: {err}, falling back to local")
        
        # Fallback на локальный метод
        if not self._local_available:
            return None
        
        try:
            result = await qr_utils.async_scan_image(self.hass, file_path)
            if result:
                result["timestamp"] = datetime.now().timestamp()
            return result
            
        except Exception as err:
            _LOGGER.error(f"Error scanning QR file: {err}")
            return None

    async def _capture_snapshot_bytes(self) -> Optional[bytes]:
        """Capture snapshot and return bytes."""
        try:
            import aiohttp
            url = f"http://{self.recorder.host}:{self.recorder.port}/image.jpg"
            auth = aiohttp.BasicAuth(self.recorder.username, self.recorder.password)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth, timeout=10) as response:
                    if response.status == 200:
                        data = await response.read()
                        if len(data) > 1000:
                            return data
            return None
        except Exception as err:
            _LOGGER.debug("Snapshot capture failed: %s", err)
            return None

    async def _capture_snapshot(self, snapshot_path: str) -> bool:
        """Capture snapshot from camera to file."""
        try:
            data = await self._capture_snapshot_bytes()
            if data:
                async with aiofiles.open(snapshot_path, 'wb') as f:
                    await f.write(data)
                return True
            return False
        except Exception as err:
            _LOGGER.debug("Snapshot capture failed: %s", err)
            return False

    async def async_setup_triggers(self, triggers: List[dict]):
        """Setup state triggers for automatic activation."""
        self._triggers = []
        for trigger_config in triggers:
            trigger = QRTrigger(
                entity_id=trigger_config["entity_id"],
                to_state=trigger_config.get("to_state", "on"),
                from_state=trigger_config.get("from_state")
            )
            self._triggers.append(trigger)
            
            async_track_state_change(
                self.hass,
                trigger.entity_id,
                self._async_trigger_state_changed
            )
            
            _LOGGER.info(f"✅ QR trigger added for {trigger.entity_id}")

    async def _async_trigger_state_changed(self, entity_id, old_state, new_state):
        """Handle trigger state changes."""
        if not new_state:
            return
            
        for trigger in self._triggers:
            if trigger.entity_id == entity_id:
                if trigger.to_state == new_state.state:
                    if not trigger.from_state or trigger.from_state == (old_state.state if old_state else None):
                        await self.async_activate(f"trigger_{entity_id}")
                        trigger.active = True
                        self._active_triggers.add(id(trigger))
                
                elif trigger.active and trigger.to_state != new_state.state:
                    self._active_triggers.discard(id(trigger))
                    if not self._active_triggers:
                        await self.async_deactivate()

    async def async_activate(self, reason: str = "manual", timeout: int = None):
        """Activate QR scanning."""
        if not self.available:
            _LOGGER.warning("QR scanner not available")
            return
            
        if self._mode == QRMode.DISABLED:
            _LOGGER.warning("QR scanning is disabled")
            return
            
        if self._scan_task and not self._scan_task.done():
            if timeout:
                self._active_until = datetime.now() + timedelta(seconds=timeout)
            _LOGGER.debug(f"QR scanning already active, extended until {self._active_until}")
            return
            
        _LOGGER.info(f"🔍 QR scanning activated: {reason}")
        
        timeout = timeout or self._scan_timeout
        self._active_until = datetime.now() + timedelta(seconds=timeout)
        
        self._scan_task = asyncio.create_task(self._scan_loop())

    async def async_deactivate(self):
        """Deactivate QR scanning."""
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
                
        self._scan_task = None
        self._active_until = None
        _LOGGER.info("🔍 QR scanning deactivated")

    async def _scan_loop(self):
        """Main scanning loop."""
        _LOGGER.info("🔄 QR scan loop started")
        
        try:
            while True:
                if self._active_until and datetime.now() > self._active_until:
                    _LOGGER.info("⏱️ QR scan timeout reached")
                    await self.async_deactivate()
                    break
                
                result = await self.async_scan_snapshot()
                
                if result:
                    _LOGGER.info(f"✅ QR Code detected: {result['data']}")
                    
                    self._last_result = result
                    self._last_time = result["timestamp"]
                    
                    # Отправляем событие в HA с правильными данными
                    event_data = {
                        "camera": self.camera_entity,
                        "data": result["data"],
                        "type": result["type"],
                        "timestamp": result["timestamp"]
                    }
                    
                    _LOGGER.debug(f"📤 Firing event openipc_qr_detected with data: {event_data}")
                    self.hass.bus.async_fire("openipc_qr_detected", event_data)
                    
                    # Если режим SINGLE, отключаемся после первого обнаружения
                    if self._mode == QRMode.SINGLE:
                        _LOGGER.info("Single mode - stopping after first detection")
                        await self.async_deactivate()
                        break
                
                await asyncio.sleep(self._scan_interval)
                
        except asyncio.CancelledError:
            _LOGGER.debug("QR scan loop cancelled")
        except Exception as err:
            _LOGGER.error(f"Error in QR scan loop: {err}")

    @property
    def last_result(self) -> Optional[Dict[str, Any]]:
        return self._last_result

    @property
    def is_active(self) -> bool:
        return self._scan_task is not None and not self._scan_task.done()

    @property
    def mode(self) -> QRMode:
        return self._mode

    @mode.setter
    def mode(self, value: QRMode):
        self._mode = value
        _LOGGER.info(f"QR mode set to {value.name}")

    @property
    def scan_interval(self) -> float:
        return self._scan_interval

    @scan_interval.setter
    def scan_interval(self, value: float):
        self._scan_interval = max(0.5, min(10.0, value))

    @property
    def scan_timeout(self) -> int:
        return self._scan_timeout

    @scan_timeout.setter
    def scan_timeout(self, value: int):
        self._scan_timeout = max(5, min(300, value))
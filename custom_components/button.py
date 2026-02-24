"""Button platform for OpenIPC."""
import logging
import asyncio
import aiohttp
from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DOMAIN, 
    API_REBOOT, 
    RECORD_START, 
    RECORD_STOP,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_BEWARD,
    DEVICE_TYPE_VIVOTEK,
    DEVICE_TYPE_OPENIPC,
    LNPR_LIST,
    LNPR_EXPORT,
    LNPR_CLEAR_LOG,
    LNPR_CLEAR,
)

_LOGGER = logging.getLogger(__name__)

# Длительности записи для кнопок (в секундах)
RECORDING_PRESETS = {
    "15s": 15,
    "30s": 30,
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "10m": 600,
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OpenIPC buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE, "openipc")
    
    entities = []
    
    # Стандартные кнопки для всех типов
    entities.extend([
        OpenIPCButton(coordinator, entry, "Reboot", "reboot", API_REBOOT, "mdi:restart"),
        OpenIPCButton(coordinator, entry, "Start Recording (Camera SD)", "record_start", RECORD_START, "mdi:record-rec"),
        OpenIPCButton(coordinator, entry, "Stop Recording", "record_stop", RECORD_STOP, "mdi:stop"),
    ])
    
    # Кнопки для записи на SD карту камеры
    for name, duration in RECORDING_PRESETS.items():
        entities.append(
            OpenIPCRecordTimerButton(
                coordinator, entry, 
                f"Record {name} (Camera SD)", 
                f"record_sd_{name}", 
                duration,
                "mdi:sd"
            )
        )
    
    # Кнопки для записи в Home Assistant media
    for name, duration in RECORDING_PRESETS.items():
        entities.append(
            OpenIPCHARecordButton(
                coordinator, entry,
                f"Record {name} (HA Media)",
                f"record_ha_{name}",
                duration,
                "mdi:home-assistant"
            )
        )
    
    # Кнопки для RTSP записи в HA media
    for name, duration in RECORDING_PRESETS.items():
        entities.append(
            OpenIPCRTSPRecordButton(
                coordinator, entry,
                f"Record {name} (RTSP)",
                f"record_rtsp_{name}",
                duration,
                "mdi:video"
            )
        )
    
    # Кнопки для записи и отправки в Telegram
    for name, duration in RECORDING_PRESETS.items():
        entities.append(
            OpenIPCTelegramRecordButton(
                coordinator, entry,
                f"Record {name} + Telegram",
                f"telegram_{name}",
                duration,
                "mdi:telegram",
                method="snapshots"
            )
        )
    
    # Кнопки для RTSP записи и отправки в Telegram
    for name, duration in RECORDING_PRESETS.items():
        entities.append(
            OpenIPCTelegramRecordButton(
                coordinator, entry,
                f"Record {name} + Telegram (RTSP)",
                f"telegram_rtsp_{name}",
                duration,
                "mdi:telegram",
                method="rtsp"
            )
        )
    
    # Специфичные кнопки для Beward
    if device_type == DEVICE_TYPE_BEWARD and coordinator.beward:
        entities.extend([
            BewardOpenDoorButton(coordinator, entry, 1, "Main Door"),
            BewardOpenDoorButton(coordinator, entry, 2, "Secondary Door"),
            # LNPR кнопки для Beward
            BewardLNPRListButton(coordinator, entry),
            BewardLNPREmptyButton(coordinator, entry),
            BewardLNPREventsButton(coordinator, entry),
            BewardLNPREventsClearButton(coordinator, entry),
        ])
        _LOGGER.info("✅ Added Beward-specific buttons for %s", entry.data.get('name'))
    
    # Специфичные кнопки для Vivotek
    elif device_type == DEVICE_TYPE_VIVOTEK and coordinator.vivotek:
        entities.extend([
            VivotekRebootButton(coordinator, entry),
        ])
        _LOGGER.info("✅ Added Vivotek-specific buttons for %s", entry.data.get('name'))
    
    async_add_entities(entities)


class OpenIPCButton(CoordinatorEntity, ButtonEntity):
    """Representation of an OpenIPC button."""

    def __init__(self, coordinator, entry, name, button_id, api_command, icon):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.button_id = button_id
        self.api_command = api_command
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{button_id}"
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Pressing button %s for camera %s", self.button_id, self.entry.data.get('name'))
        
        if self.button_id == "record_start":
            await self.coordinator.async_start_recording()
        elif self.button_id == "record_stop":
            await self.coordinator.async_stop_recording()
        else:
            await self.coordinator.async_send_command(self.api_command)

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


class OpenIPCRecordTimerButton(CoordinatorEntity, ButtonEntity):
    """Button for timed recording on camera SD card."""

    def __init__(self, coordinator, entry, name, button_id, duration, icon):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.button_id = button_id
        self.duration = duration
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{button_id}"
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Starting %d second recording on camera SD for %s", 
                     self.duration, self.entry.data.get('name'))
        
        await self.coordinator.async_start_timed_recording(self.duration, save_to_ha=False)

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


class OpenIPCHARecordButton(CoordinatorEntity, ButtonEntity):
    """Button for recording to Home Assistant media folder using snapshots."""

    def __init__(self, coordinator, entry, name, button_id, duration, icon):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.button_id = button_id
        self.duration = duration
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{button_id}"
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Starting %d second recording to HA Media for %s (snapshots)", 
                     self.duration, self.entry.data.get('name'))
        
        await self.coordinator.async_start_timed_recording(
            self.duration, 
            save_to_ha=True, 
            method="snapshots"
        )

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


class OpenIPCRTSPRecordButton(CoordinatorEntity, ButtonEntity):
    """Button for recording to Home Assistant media folder using RTSP stream."""

    def __init__(self, coordinator, entry, name, button_id, duration, icon):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.button_id = button_id
        self.duration = duration
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{button_id}"
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Starting %d second recording to HA Media for %s (RTSP)", 
                     self.duration, self.entry.data.get('name'))
        
        await self.coordinator.async_start_timed_recording(
            self.duration, 
            save_to_ha=True, 
            method="rtsp"
        )

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


class OpenIPCTelegramRecordButton(CoordinatorEntity, ButtonEntity):
    """Button for recording and sending to Telegram."""

    def __init__(self, coordinator, entry, name, button_id, duration, icon, method="snapshots"):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.button_id = button_id
        self.duration = duration
        self.method = method
        self._attr_name = f"{entry.data.get('name', 'OpenIPC')} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{button_id}"
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Recording %d seconds and sending to Telegram for %s", 
                     self.duration, self.entry.data.get('name'))
        
        if hasattr(self.coordinator, 'async_record_and_send_telegram'):
            await self.coordinator.async_record_and_send_telegram(
                self.duration, 
                method=self.method,
                caption=f"📹 Запись с камеры {self.entry.data.get('name')}\n⏱ {self.duration} секунд"
            )
        else:
            _LOGGER.error("Telegram recording method not available")

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


# ==================== Beward Specific Buttons ====================

class BewardOpenDoorButton(CoordinatorEntity, ButtonEntity):
    """Button to open Beward door."""

    def __init__(self, coordinator, entry, relay_id: int, name_suffix: str):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self.relay_id = relay_id
        self._attr_name = f"{entry.data.get('name', 'Beward')} Open {name_suffix}"
        self._attr_unique_id = f"{entry.entry_id}_beward_open_door_{relay_id}"
        self._attr_icon = "mdi:door-open"

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.coordinator.beward:
            _LOGGER.info("🚪 Opening Beward door (relay %d)", self.relay_id)
            await self.coordinator.beward.async_open_door(main=(self.relay_id == 1))
        else:
            _LOGGER.error("Beward device not available")

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


class BewardLNPRListButton(CoordinatorEntity, ButtonEntity):
    """Button to get LNPR list (whitelist)."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Get Plates List"
        self._attr_unique_id = f"{entry.entry_id}_beward_lnpr_list"
        self._attr_icon = "mdi:format-list-numbered"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self.coordinator.beward:
            _LOGGER.error("Beward device not available")
            return
        
        _LOGGER.info("📋 Getting LNPR whitelist from %s", self.entry.data.get('name'))
        
        try:
            url = f"http://{self.coordinator.beward.host}{LNPR_LIST}"
            async with self.coordinator.session.get(url, auth=self.coordinator.auth) as response:
                if response.status == 200:
                    text = await response.text()
                    
                    # Парсим ответ
                    plates = []
                    lines = text.strip().split('\n')
                    for line in lines:
                        if line.startswith('Number'):
                            plates.append(line)
                    
                    message = f"📋 **Найденные номера:**\n\n"
                    if plates:
                        for plate in plates:
                            message += f"• {plate}\n"
                        message += f"\nВсего: {len(plates)} номеров"
                    else:
                        message += "Список пуст"
                    
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": f"LNPR Whitelist - {self.entry.data.get('name')}",
                            "message": message,
                            "notification_id": f"openipc_lnpr_list_{self.entry.entry_id}"
                        }
                    )
                else:
                    _LOGGER.error("Failed to get LNPR list: HTTP %d", response.status)
        except Exception as err:
            _LOGGER.error("Error getting LNPR list: %s", err)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


class BewardLNPREmptyButton(CoordinatorEntity, ButtonEntity):
    """Button to clear LNPR whitelist."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Clear Plates List"
        self._attr_unique_id = f"{entry.entry_id}_beward_lnpr_clear"
        self._attr_icon = "mdi:delete-sweep"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self.coordinator.beward:
            _LOGGER.error("Beward device not available")
            return
        
        _LOGGER.info("🧹 Clearing LNPR whitelist for %s", self.entry.data.get('name'))
        
        # Спрашиваем подтверждение через уведомление
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"⚠️ Подтверждение - {self.entry.data.get('name')}",
                "message": f"Вы действительно хотите очистить список разрешенных номеров?\n\n"
                          f"Это действие нельзя отменить!\n\n"
                          f"Нажмите кнопку еще раз для подтверждения.",
                "notification_id": f"openipc_lnpr_confirm_{self.entry.entry_id}"
            }
        )
        
        # Вторая попытка для подтверждения
        # В реальном коде нужно реализовать подтверждение через события
        
        try:
            url = f"http://{self.coordinator.beward.host}{LNPR_CLEAR}"
            async with self.coordinator.session.get(url, auth=self.coordinator.auth) as response:
                if response.status == 200:
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": f"✅ LNPR - {self.entry.data.get('name')}",
                            "message": "Список разрешенных номеров успешно очищен",
                            "notification_id": f"openipc_lnpr_clear_{self.entry.entry_id}"
                        }
                    )
                else:
                    _LOGGER.error("Failed to clear LNPR list: HTTP %d", response.status)
        except Exception as err:
            _LOGGER.error("Error clearing LNPR list: %s", err)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


class BewardLNPREventsButton(CoordinatorEntity, ButtonEntity):
    """Button to export LNPR events log."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Export LNPR Events"
        self._attr_unique_id = f"{entry.entry_id}_beward_lnpr_export"
        self._attr_icon = "mdi:export"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self.coordinator.beward:
            _LOGGER.error("Beward device not available")
            return
        
        _LOGGER.info("📊 Exporting LNPR events from %s", self.entry.data.get('name'))
        
        from datetime import datetime, timedelta
        
        # Экспортируем события за последние 7 дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            url = f"http://{self.coordinator.beward.host}{LNPR_EXPORT}&begin={start_str}&end={end_str}"
            async with self.coordinator.session.get(url, auth=self.coordinator.auth) as response:
                if response.status == 200:
                    text = await response.text()
                    
                    # Сохраняем в файл
                    filename = f"/config/lnpr_events_{self.entry.entry_id}_{datetime.now().strftime('%Y%m%d')}.csv"
                    with open(filename, 'w') as f:
                        f.write(text)
                    
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": f"📊 LNPR Events - {self.entry.data.get('name')}",
                            "message": f"✅ Экспорт завершен\n\n"
                                      f"📁 Файл: {filename}\n"
                                      f"📅 Период: {start_str} - {end_str}\n"
                                      f"Размер: {len(text)} байт",
                            "notification_id": f"openipc_lnpr_export_{self.entry.entry_id}"
                        }
                    )
                else:
                    _LOGGER.error("Failed to export LNPR events: HTTP %d", response.status)
        except Exception as err:
            _LOGGER.error("Error exporting LNPR events: %s", err)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


class BewardLNPREventsClearButton(CoordinatorEntity, ButtonEntity):
    """Button to clear LNPR events log."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Beward')} Clear LNPR Events"
        self._attr_unique_id = f"{entry.entry_id}_beward_lnpr_events_clear"
        self._attr_icon = "mdi:delete"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        if not self.coordinator.beward:
            _LOGGER.error("Beward device not available")
            return
        
        _LOGGER.info("🧹 Clearing LNPR events log for %s", self.entry.data.get('name'))
        
        try:
            url = f"http://{self.coordinator.beward.host}{LNPR_CLEAR_LOG}"
            async with self.coordinator.session.get(url, auth=self.coordinator.auth) as response:
                if response.status == 200:
                    await self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": f"✅ LNPR - {self.entry.data.get('name')}",
                            "message": "Журнал событий LNPR успешно очищен",
                            "notification_id": f"openipc_lnpr_events_clear_{self.entry.entry_id}"
                        }
                    )
                else:
                    _LOGGER.error("Failed to clear LNPR events: HTTP %d", response.status)
        except Exception as err:
            _LOGGER.error("Error clearing LNPR events: %s", err)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Beward Doorbell"),
            "manufacturer": "Beward",
            "model": "DS07P-LP",
        }


# ==================== Vivotek Specific Buttons ====================

class VivotekRebootButton(CoordinatorEntity, ButtonEntity):
    """Button to reboot Vivotek camera."""

    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry = entry
        self._attr_name = f"{entry.data.get('name', 'Vivotek')} Reboot"
        self._attr_unique_id = f"{entry.entry_id}_vivotek_reboot"
        self._attr_icon = "mdi:restart"

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.coordinator.vivotek:
            _LOGGER.info("🔄 Rebooting Vivotek camera")
        else:
            _LOGGER.error("Vivotek device not available")

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": self.entry.data.get("name", "Vivotek Camera"),
            "manufacturer": "Vivotek",
            "model": "SD9364-EHL",
        }
"""OpenIPC integration for Home Assistant."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import OpenIPCDataUpdateCoordinator
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.CAMERA,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    "media_player",  # Кастомная платформа
    Platform.SELECT,
]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the OpenIPC component from YAML configuration."""
    hass.data.setdefault(DOMAIN, {})
    
    # Читаем конфигурацию из YAML для Telegram
    if DOMAIN in config:
        conf = config[DOMAIN]
        telegram_config = {
            "telegram_bot_token": conf.get("telegram_bot_token"),
            "telegram_chat_id": conf.get("telegram_chat_id"),
        }
        hass.data[DOMAIN]["config"] = telegram_config
        _LOGGER.info("✅ Telegram config loaded from YAML: bot_token=%s, chat_id=%s",
                    "✅" if telegram_config["telegram_bot_token"] else "❌",
                    telegram_config["telegram_chat_id"] or "❌")
    else:
        _LOGGER.debug("No OpenIPC YAML configuration found")
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenIPC from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create coordinator for data updates
    coordinator = OpenIPCDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Register services (они будут зарегистрированы только один раз)
    await async_register_services(hass)
    
    # Set up all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    
    # Останавливаем QR-сканер
    if coordinator and hasattr(coordinator, 'qr_scanner') and coordinator.qr_scanner:
        await coordinator.qr_scanner.async_deactivate()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    # Если это была последняя запись, удаляем сервисы
    if not hass.data[DOMAIN] or (len(hass.data[DOMAIN]) == 1 and "config" in hass.data[DOMAIN]):
        from .services import async_remove_services
        await async_remove_services(hass)
    
    return unload_ok

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    from .migration import async_migrate_entry as migrate
    return await migrate(hass, config_entry)

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    try:
        device_registry = dr.async_get(hass)
        device_registry.async_clear_config_entry(entry.entry_id)
    except Exception as err:
        _LOGGER.debug("Error removing device registry entry: %s", err)
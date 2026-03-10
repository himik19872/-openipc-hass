"""Helper functions for OpenIPC integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def find_coordinator_by_entity_id(hass: HomeAssistant, entity_id: str):
    """Find coordinator by entity_id - improved version."""
    _LOGGER.debug("🔍 Looking for coordinator with entity_id: %s", entity_id)
    
    if not entity_id:
        return None
    
    if isinstance(entity_id, list):
        if entity_id:
            entity_id = entity_id[0]
        else:
            return None
    
    if not isinstance(entity_id, str):
        return None
    
    # Сначала пытаемся найти по точному совпадению для камеры
    for entry_id, coordinator in hass.data[DOMAIN].items():
        if entry_id == "config":
            continue
        
        if not hasattr(coordinator, 'recorder'):
            continue
        
        camera_name = coordinator.recorder.camera_name
        camera_host = coordinator.host
        
        # Проверяем различные варианты entity_id камеры
        exact_ids = [
            f"camera.{camera_name}",
            f"camera.{camera_host.replace('.', '_')}",
            f"camera.{camera_host}",
        ]
        
        if entity_id in exact_ids:
            _LOGGER.debug("✅ Found coordinator by exact match: %s", entry_id)
            return coordinator
    
    # Если не нашли по точному совпадению, ищем через device registry
    try:
        from homeassistant.helpers import device_registry as dr, entity_registry as er
        
        entity_reg = er.async_get(hass)
        entity_entry = entity_reg.async_get(entity_id)
        
        if entity_entry and entity_entry.device_id:
            device_reg = dr.async_get(hass)
            device = device_reg.async_get(entity_entry.device_id)
            
            if device:
                # Ищем координатор по идентификатору устройства
                for entry_id, coordinator in hass.data[DOMAIN].items():
                    if entry_id == "config":
                        continue
                    
                    # Проверяем, принадлежит ли устройство этому координатору
                    if (DOMAIN, entry_id) in device.identifiers:
                        _LOGGER.debug("✅ Found coordinator via device registry: %s", entry_id)
                        return coordinator
    except Exception as err:
        _LOGGER.debug("Error in device registry lookup: %s", err)
    
    # Если все еще не нашли, пробуем по частичному совпадению имени
    entity_lower = entity_id.lower()
    for entry_id, coordinator in hass.data[DOMAIN].items():
        if entry_id == "config":
            continue
        
        if hasattr(coordinator, 'recorder'):
            camera_name = coordinator.recorder.camera_name.lower()
            camera_host = coordinator.host
            
            if camera_name in entity_lower or camera_host in entity_lower:
                _LOGGER.debug("✅ Found coordinator by partial match: %s", entry_id)
                return coordinator
    
    _LOGGER.error("❌ Coordinator not found for %s", entity_id)
    return None

async def find_media_player(hass: HomeAssistant, entity_id: str):
    """Find media player entity by entity_id."""
    if not entity_id:
        return None
    component: EntityComponent = hass.data.get("entity_components", {}).get("media_player")
    if component:
        for entity in component.entities:
            if entity.entity_id == entity_id:
                return entity
    return None

async def find_button(hass: HomeAssistant, entity_id: str):
    """Find button entity by entity_id."""
    if not entity_id:
        return None
    component: EntityComponent = hass.data.get("entity_components", {}).get("button")
    if component:
        for entity in component.entities:
            if entity.entity_id == entity_id:
                return entity
    return None

async def find_switch(hass: HomeAssistant, entity_id: str):
    """Find switch entity by entity_id."""
    if not entity_id:
        return None
    component: EntityComponent = hass.data.get("entity_components", {}).get("switch")
    if component:
        for entity in component.entities:
            if entity.entity_id == entity_id:
                return entity
    return None
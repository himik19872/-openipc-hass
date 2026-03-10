"""Migration functions for OpenIPC integration."""
import logging

from homeassistant.const import CONF_DEVICE_TYPE

from .const import DEVICE_TYPE_OPENIPC

_LOGGER = logging.getLogger(__name__)

async def async_migrate_entry(hass, config_entry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)
    
    if config_entry.version == 1:
        new_data = {**config_entry.data}
        
        if CONF_DEVICE_TYPE not in new_data:
            new_data[CONF_DEVICE_TYPE] = DEVICE_TYPE_OPENIPC
        
        hass.config_entries.async_update_entry(
            config_entry, 
            data=new_data,
            version=2
        )
        _LOGGER.info("✅ Migrated entry from version 1 to 2")
    
    return True
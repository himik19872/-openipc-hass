"""QR code utilities with lazy imports to avoid blocking."""
import logging
import asyncio
from functools import partial
from typing import Optional, Dict, Any

_LOGGER = logging.getLogger(__name__)

# Ленивый импорт - библиотеки загружаются только при первом использовании
_pyzbar_available = None
_pil_available = None

def _check_libraries():
    """Check if required libraries are available (runs in executor)."""
    global _pyzbar_available, _pil_available
    
    if _pyzbar_available is not None and _pil_available is not None:
        return _pyzbar_available and _pil_available
    
    pyzbar_ok = False
    pil_ok = False
    
    try:
        import pyzbar.pyzbar
        pyzbar_ok = True
        _LOGGER.debug("✅ pyzbar loaded successfully")
    except ImportError as e:
        _LOGGER.debug("❌ pyzbar not available: %s", e)
    
    try:
        from PIL import Image
        pil_ok = True
        _LOGGER.debug("✅ PIL loaded successfully")
    except ImportError as e:
        _LOGGER.debug("❌ PIL not available: %s", e)
    
    _pyzbar_available = pyzbar_ok
    _pil_available = pil_ok
    
    return pyzbar_ok and pil_ok

async def async_check_libraries(hass) -> bool:
    """Check libraries without blocking the event loop."""
    return await hass.async_add_executor_job(_check_libraries)

async def async_scan_image(hass, image_path: str) -> Optional[Dict[str, Any]]:
    """Scan image for QR codes in executor."""
    return await hass.async_add_executor_job(_scan_image_sync, image_path)

def _scan_image_sync(image_path: str) -> Optional[Dict[str, Any]]:
    """Synchronous QR code scanning."""
    if not _check_libraries():
        return None
    
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode
        
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        decoded_objects = decode(img)
        
        if not decoded_objects:
            return None
        
        qr = decoded_objects[0]
        
        return {
            "data": qr.data.decode('utf-8'),
            "type": qr.type,
            "rect": {
                "left": qr.rect.left,
                "top": qr.rect.top,
                "width": qr.rect.width,
                "height": qr.rect.height
            }
        }
    except Exception as err:
        _LOGGER.error("QR scan error: %s", err)
        return None
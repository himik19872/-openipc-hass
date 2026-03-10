"""LNPR (License Plate Recognition) functions for Beward cameras."""
import logging
import async_timeout

_LOGGER = logging.getLogger(__name__)

async def async_update_lnpr(coordinator):
    """Fetch LNPR data from camera."""
    if not coordinator.beward:
        return {}
    
    lnpr_data = {
        "last_number": "none",
        "last_direction": "unknown",
        "last_time": "none",
        "last_coordinates": "",
        "last_size": "",
        "last_authorized": False,
        "total_today": 0,
        "authorized_count": 0,
        "enabled": True,
    }
    
    try:
        url = f"http://{coordinator.host}:{coordinator.port}/cgi-bin/lnprstate_cgi"
        async with async_timeout.timeout(5):
            async with coordinator.session.get(url, auth=coordinator.auth) as response:
                if response.status == 200:
                    text = await response.text()
                    lines = text.strip().split('\n')
                    for line in lines:
                        if line and not line.startswith('--'):
                            parts = line.split()
                            if len(parts) >= 5:
                                date_time = f"{parts[0]} {parts[1]}"
                                number = parts[2]
                                coords = parts[3]
                                size = parts[4]
                                direction = parts[5] if len(parts) > 5 else "unknown"
                                
                                lnpr_data["last_number"] = number
                                lnpr_data["last_direction"] = direction
                                lnpr_data["last_time"] = date_time
                                lnpr_data["last_coordinates"] = coords
                                lnpr_data["last_size"] = size
                                
                                lnpr_data["last_authorized"] = await check_plate_authorized(coordinator, number)
    
    except Exception as err:
        _LOGGER.debug("Error fetching LNPR data: %s", err)
    
    return lnpr_data

async def check_plate_authorized(coordinator, plate: str) -> bool:
    """Check if plate is in whitelist."""
    try:
        url = f"http://{coordinator.host}:{coordinator.port}/cgi-bin/lnpr_cgi?action=list"
        async with coordinator.session.get(url, auth=coordinator.auth, timeout=5) as response:
            if response.status == 200:
                text = await response.text()
                return plate in text
    except:
        pass
    return False
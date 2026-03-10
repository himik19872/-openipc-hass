"""Camera commands for OpenIPC."""

async def set_night_mode(coordinator, mode: str):
    """Set night mode (on/off/auto)."""
    if mode == "on":
        return await coordinator.async_send_command("/night/on")
    elif mode == "off":
        return await coordinator.async_send_command("/night/off")
    elif mode == "auto":
        return await coordinator.async_send_command("/night/auto")
    return False
"""Recording functions for OpenIPC cameras."""
import asyncio
import logging

from .const import RECORD_START, RECORD_STOP, RECORD_STATUS, RECORD_MANUAL

_LOGGER = logging.getLogger(__name__)

async def start_recording(coordinator):
    """Start recording on camera SD card."""
    if coordinator.is_beward or coordinator.is_vivotek:
        _LOGGER.warning("Recording not supported for this device")
        return False
    
    _LOGGER.info("Starting recording on camera %s", coordinator.host)
    
    endpoints = [
        RECORD_START,
        "/cgi-bin/record.cgi?action=start",
        "/api/v1/record?action=start",
    ]
    
    for endpoint in endpoints:
        if await coordinator.async_send_command(endpoint):
            _LOGGER.info("Recording started via %s", endpoint)
            coordinator._recording_end_time = None
            return True
    
    _LOGGER.error("Failed to start recording")
    return False

async def stop_recording(coordinator):
    """Stop recording on camera SD card."""
    if coordinator.is_beward or coordinator.is_vivotek:
        _LOGGER.warning("Recording not supported for this device")
        return False
    
    _LOGGER.info("Stopping recording on camera %s", coordinator.host)
    
    if coordinator._recording_task:
        coordinator._recording_task.cancel()
        coordinator._recording_task = None
    
    if coordinator._ha_recording_task and not coordinator._ha_recording_task.done():
        coordinator._ha_recording_task.cancel()
    
    endpoints = [
        RECORD_STOP,
        "/cgi-bin/record.cgi?action=stop",
        "/api/v1/record?action=stop",
    ]
    
    for endpoint in endpoints:
        if await coordinator.async_send_command(endpoint):
            _LOGGER.info("Recording stopped via %s", endpoint)
            coordinator._recording_end_time = None
            return True
    
    _LOGGER.error("Failed to stop recording")
    return False

async def get_recording_status(coordinator):
    """Get recording status."""
    endpoints = [
        RECORD_STATUS,
        "/cgi-bin/record.cgi?action=status",
        "/api/v1/record/status",
    ]
    
    for endpoint in endpoints:
        try:
            url = f"http://{coordinator.host}:{coordinator.port}{endpoint}"
            async with coordinator.session.get(url, auth=coordinator.auth, timeout=3) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        return data
                    except:
                        text = await response.text()
                        if "recording" in text.lower():
                            return {
                                "recording": "active" in text.lower() or "true" in text.lower(),
                                "raw": text
                            }
        except:
            continue
    
    if coordinator._recording_end_time:
        remaining = coordinator._recording_end_time - coordinator.hass.loop.time()
        if remaining > 0:
            return {
                "recording": True,
                "remaining": int(remaining),
                "end_time": coordinator._recording_end_time,
            }
    
    return {"recording": False}

async def record_to_ha_media(coordinator, duration: int, method: str = "snapshots") -> dict:
    """Record video directly to Home Assistant media folder."""
    _LOGGER.info("Starting HA media recording for %d seconds using %s", duration, method)
    
    if method == "rtsp":
        result = await coordinator.recorder.record_rtsp_stream(duration, "main", False)
    else:
        result = await coordinator.recorder.record_video(duration)
    
    if result.get("success"):
        await coordinator.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"📹 Запись с камеры {coordinator.recorder.camera_name}",
                "message": f"✅ Видео сохранено:\n"
                          f"📁 {result['filename']}\n"
                          f"⏱ Длительность: {duration} сек\n"
                          f"📊 Размер: {result['size'] / 1024:.1f} KB\n"
                          f"📍 {result['url']}",
                "notification_id": f"openipc_recording_{coordinator.entry.entry_id}"
            },
            blocking=True
        )
    
    return result

async def start_timed_recording(coordinator, duration: int, save_to_ha: bool = True, method: str = "snapshots"):
    """Start recording for specified duration."""
    _LOGGER.info("Starting %d second recording on camera %s (save_to_ha=%s)", 
                 duration, coordinator.host, save_to_ha)
    
    if save_to_ha:
        if coordinator._ha_recording_task and not coordinator._ha_recording_task.done():
            coordinator._ha_recording_task.cancel()
        
        coordinator._ha_recording_task = asyncio.create_task(
            record_to_ha_media(coordinator, duration, method)
        )
        
        coordinator._recording_end_time = coordinator.hass.loop.time() + duration
        return True
    else:
        if coordinator.is_beward or coordinator.is_vivotek:
            _LOGGER.warning("SD card recording not supported for this device")
            return False
            
        await stop_recording(coordinator)
        await asyncio.sleep(1)
        
        duration_url = RECORD_MANUAL.format(duration)
        if await coordinator.async_send_command(duration_url):
            _LOGGER.info("Timed recording started via %s", duration_url)
            coordinator._recording_end_time = coordinator.hass.loop.time() + duration
            return True
        
        if await start_recording(coordinator):
            coordinator._recording_end_time = coordinator.hass.loop.time() + duration
            
            async def stop_after_delay():
                try:
                    await asyncio.sleep(duration)
                    await stop_recording(coordinator)
                except asyncio.CancelledError:
                    _LOGGER.debug("Recording timer cancelled")
            
            coordinator._recording_task = asyncio.create_task(stop_after_delay())
            return True
        
        return False

async def record_and_send_telegram(coordinator, duration: int, method: str = "snapshots",
                                  caption: str = None, chat_id: str = None) -> dict:
    """Record video and send to Telegram."""
    _LOGGER.info("Recording and sending to Telegram for %d seconds", duration)
    
    result = await coordinator.recorder.record_and_send_to_telegram(
        duration, method, caption, chat_id
    )
    
    if result.get("success") and result.get("telegram_sent"):
        await coordinator.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"📹 Запись с камеры {coordinator.recorder.camera_name}",
                "message": f"✅ Видео сохранено и отправлено в Telegram!\n"
                          f"📁 {result['filename']}\n"
                          f"⏱ Длительность: {duration} сек\n"
                          f"📊 Размер: {result['size'] / 1024:.1f} KB",
                "notification_id": f"openipc_telegram_{coordinator.entry.entry_id}"
            },
            blocking=True
        )
    elif result.get("success"):
        await coordinator.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"📹 Запись с камеры {coordinator.recorder.camera_name}",
                "message": f"✅ Видео сохранено, но НЕ отправлено в Telegram.\n"
                          f"📁 {result['filename']}\n"
                          f"⏱ Длительность: {duration} сек",
                "notification_id": f"openipc_telegram_{coordinator.entry.entry_id}"
            },
            blocking=True
        )
    
    return result
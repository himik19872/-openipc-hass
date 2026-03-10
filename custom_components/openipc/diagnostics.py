"""Diagnostic functions for OpenIPC cameras."""
import logging

_LOGGER = logging.getLogger(__name__)

async def diagnose_rtsp(coordinator):
    """Diagnose RTSP stream."""
    if hasattr(coordinator, 'recorder'):
        results = await coordinator.recorder.diagnose_rtsp()
        
        message = "📹 **RTSP Diagnostic Results**\n\n"
        working_paths = []
        
        for path, result in results.items():
            status = "✅" if result["success"] else "❌"
            message += f"{status} `{path}`\n"
            if result["success"]:
                working_paths.append(path)
            elif result.get("error"):
                message += f"   Error: {result['error'][:100]}\n"
        
        if working_paths:
            message += f"\n**Working paths:**\n"
            for path in working_paths:
                message += f"- `{path}`\n"
            message += "\n**Recommended path for configuration:**\n"
            message += f"`{working_paths[0]}`"
        else:
            message += "\n❌ No working RTSP paths found!\n"
            message += "\n**Troubleshooting:**\n"
            message += "1. Check if camera is powered on\n"
            message += "2. Verify RTSP port (default 554)\n"
            message += "3. Check firewall settings\n"
            message += "4. Try different stream paths in config\n"
            message += "5. Verify RTSP is enabled in camera settings"
        
        await coordinator.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"RTSP Diagnosis - {coordinator.recorder.camera_name}",
                "message": message,
                "notification_id": f"openipc_rtsp_diagnose_{coordinator.entry.entry_id}"
            },
            blocking=True
        )
        
        return results
    return None

async def diagnose_telegram(coordinator):
    """Diagnose Telegram configuration."""
    if hasattr(coordinator, 'recorder'):
        results = await coordinator.recorder.diagnose_telegram()
        
        message = f"📱 **Telegram Diagnostic Results for {coordinator.recorder.camera_name}**\n\n"
        message += f"• telegram_bot.send_file: {'✅' if results.get('telegram_bot_service') else '❌'}\n"
        message += f"• notify.telegram_notify: {'✅' if results.get('notify_service') else '❌'}\n"
        message += f"• Bot token configured: {'✅' if results.get('bot_token_configured') else '❌'}\n"
        message += f"• Chat ID configured: {'✅' if results.get('chat_id_configured') else '❌'}\n"
        message += f"• Available services: {results.get('available_services', [])}\n"
        
        if results.get('test_message'):
            message += f"• Test message: {results['test_message']}\n"
        
        message += "\n**Troubleshooting:**\n"
        message += "1. Configure Telegram bot via UI: Settings → Devices & Services → Add Integration → Telegram bot\n"
        message += "2. Add bot token and chat_id to openipc section in configuration.yaml for direct API\n"
        
        await coordinator.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Telegram Diagnosis",
                "message": message,
                "notification_id": f"openipc_telegram_diagnose_{coordinator.entry.entry_id}"
            },
            blocking=True
        )
        
        return results
    return None

async def test_telegram(coordinator, chat_id: str = None):
    """Test Telegram file send."""
    if hasattr(coordinator, 'recorder'):
        results = await coordinator.recorder.test_telegram_file_send(chat_id)
        return results
    return None
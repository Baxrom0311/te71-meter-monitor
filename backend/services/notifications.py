import logging
from typing import Any

import httpx

from core.config import settings
from services.websocket import ws_manager

logger = logging.getLogger(__name__)


def format_alert_message(notification: dict[str, Any]) -> str:
    severity = str(notification.get("severity") or "unknown").upper()
    kind = notification.get("kind") or "alert"
    device_id = notification.get("device_id") or "unknown-device"
    utility_type = notification.get("utility_type") or "unknown"
    message = notification.get("message") or "Alert"
    return f"[{severity}] {kind}\nDevice: {device_id}\nUtility: {utility_type}\n{message}"


async def send_internal_notification(notification: dict[str, Any], status: str = "sent") -> None:
    await ws_manager.broadcast(
        {
            "type": "alert_notification",
            "status": status,
            "severity": notification.get("severity"),
            "kind": notification.get("kind"),
            "device_id": notification.get("device_id"),
            "message": notification.get("message"),
        }
    )


async def send_telegram_notification(notification: dict[str, Any]) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram alert channel sozlanmagan")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": format_alert_message(notification),
                "disable_web_page_preview": True,
            },
        )
    response.raise_for_status()


async def send_webhook_notification(notification: dict[str, Any]) -> None:
    if not settings.alert_webhook_url:
        raise RuntimeError("Alert webhook channel sozlanmagan")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            settings.alert_webhook_url,
            json={"type": "alert_notification", "notification": notification},
        )
    response.raise_for_status()


async def send_alert_notification(notification: dict[str, Any], status: str = "sent") -> dict:
    channels = settings.alert_notification_channels or ["internal"]
    delivered: list[str] = []
    failed: list[dict[str, str]] = []
    for channel in channels:
        try:
            if channel == "internal":
                await send_internal_notification(notification, status)
            elif channel == "telegram":
                await send_telegram_notification(notification)
            elif channel == "webhook":
                await send_webhook_notification(notification)
            else:
                raise RuntimeError(f"Noma'lum notification channel: {channel}")
            delivered.append(channel)
        except Exception as exc:
            logger.exception("alert notification channel failed: %s", channel)
            failed.append({"channel": channel, "error": str(exc)})
    return {"ok": not failed, "delivered": delivered, "failed": failed}

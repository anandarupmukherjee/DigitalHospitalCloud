import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_message(message: str, **kwargs: Any) -> bool:
    """
    Send a message to the configured Telegram channel.

    Returns True when Telegram acknowledges the request.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.debug("Telegram credentials missing; skipping message: %s", message)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    payload.update(kwargs)

    try:
        response = requests.post(url, json=payload, timeout=10)
    except Exception as exc:  # pragma: no cover - network edge case
        logger.error("Failed to contact Telegram API: %s", exc)
        return False

    if not response.ok:
        logger.error(
            "Telegram rejected message (%s): %s", response.status_code, response.text
        )
        return False

    logger.info("Sent Telegram message to %s", chat_id)
    return True

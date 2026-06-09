import logging
import requests

from config.settings import SETTINGS

logger = logging.getLogger(__name__)


def send_telegram_message(message: str) -> None:
    if not SETTINGS.TELEGRAM_TOKEN or not SETTINGS.TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials are not configured. Message not sent.")
        return

    url = f"https://api.telegram.org/bot{SETTINGS.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": SETTINGS.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        logger.info("Telegram report sent")
    except Exception as exc:
        logger.error(f"Failed to send Telegram message: {exc}")

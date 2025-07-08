#!/usr/bin/env python3
"""
🚀 Entry point for ReadLater Bot - Polling only
"""

import os
import logging
import requests
from bot_logic_simplified import get_telegram_app

# לוגים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Starting ReadLater Bot...")

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return

    try:
        requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
        logger.info("🔧 Webhook deleted.")
    except Exception as e:
        logger.warning(f"⚠️ Couldn't delete webhook: {e}")

    app = get_telegram_app()
    logger.info("📡 Running polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

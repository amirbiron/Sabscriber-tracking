#!/usr/bin/env python3
"""
🚀 Entry point for Subscriber_tracking Bot - Worker Service
"""

import os
import logging
import requests
from bot_logic import SubscriberTrackingBot

# לוגים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """הפעלת הבוט"""
    logger.info("🚀 Starting Subscriber_tracking Bot...")

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return

    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
        logger.info(f"🔧 Webhook deleted: {response.json()}")
    except Exception as e:
        logger.warning(f"⚠️ Couldn't delete webhook: {e}")

    try:
        bot = SubscriberTrackingBot()
        logger.info("📡 Bot initialized")

        # Run bot inside asyncio event loop so that scheduler can start safely
        import asyncio

        async def _run_bot():
            await bot.run()

        asyncio.run(_run_bot())
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise

# 👇 הרצה פשוטה ובטוחה - ללא get_event_loop
if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
🚀 Entry point for Subscriber_tracking Bot - Worker Service
"""

import os
import logging
import requests
import asyncio
from bot_logic import SubscriberTrackingBot

# לוגים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """הפעלת Subscriber_tracking Bot"""
    logger.info("🚀 Starting Subscriber_tracking Bot...")
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return

    try:
        # מחיקת webhook כדי לא לגרום לקונפליקט
        response = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
        logger.info(f"🔧 Webhook deleted: {response.json()}")
    except Exception as e:
        logger.warning(f"⚠️ Couldn't delete webhook: {e}")

    try:
        bot = SubscriberTrackingBot()
        logger.info("📡 Bot initialized!")

        # הפעלת הסקדולר אם קיים
        if hasattr(bot, 'scheduler'):
            bot.scheduler.start(paused=False)
            logger.info("🕒 Scheduler started")

        bot.run()
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    import asyncio

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

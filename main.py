#!/usr/bin/env python3
import os
import logging
import requests
import asyncio
import nest_asyncio
from bot_logic import SubscriberTrackingBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

nest_asyncio.apply()

async def start_bot():
    logger.info("🚀 Starting Subscriber_tracking Bot...")

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        )
        logger.info(f"🔧 Webhook deleted: {response.json()}")
    except Exception as e:
        logger.warning(f"⚠️ Couldn't delete webhook: {e}")

    try:
        bot = SubscriberTrackingBot()
        logger.info("📡 Bot initialized")
        await bot.run()

    except Exception as e:
        logger.exception(f"❌ Unexpected error inside bot: {e}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    loop.run_forever()

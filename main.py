#!/usr/bin/env python3
"""
🚀 Entry point for ReadLater Bot - Polling only
"""

import os
import logging
import requests
from bot_logic import get_telegram_app

# לוגים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Starting ReadLater Bot...")

    # First check if token is available
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        logger.error("📝 Please set the TELEGRAM_BOT_TOKEN environment variable in Render:")
        logger.error("   1. Go to your Render dashboard")
        logger.error("   2. Select your service")
        logger.error("   3. Go to Environment tab")
        logger.error("   4. Add: TELEGRAM_BOT_TOKEN = your_bot_token_here")
        logger.error("   5. Redeploy the service")
        return

    try:
        requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
        logger.info("🔧 Webhook deleted.")
    except Exception as e:
        logger.warning(f"⚠️ Couldn't delete webhook: {e}")

    try:
        app = get_telegram_app()
        logger.info("📡 Running polling...")
        app.run_polling(drop_pending_updates=True)
    except ValueError as e:
        logger.error(f"❌ Bot initialization failed: {e}")
        logger.error("📝 Please check your TELEGRAM_BOT_TOKEN configuration in Render")
        return
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()

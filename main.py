#!/usr/bin/env python3
"""
🚀 Entry point for Subscriber_tracking Bot - Worker Service
"""

import os
import logging
import requests
from bot_logic import SubscriberTrackingBot
from bot_logic_simplified import get_telegram_app


# לוגים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """הפעלת Subscriber_tracking Bot"""
    logger.info("🚀 Starting Subscriber_tracking Bot...")
    
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
        # נקה webhook וודא שאין התנגשויות
        response = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
        logger.info(f"🔧 Webhook deleted: {response.json()}")
        
        # המתן קצת לפני הפעלת הבוט
        import time
        time.sleep(2)
    except Exception as e:
        logger.warning(f"⚠️ Couldn't delete webhook: {e}")

    try:
        # הפעלת הבוט
        bot = SubscriberTrackingBot()
        logger.info("📡 Bot started successfully!")
        bot.run()
        
    except ValueError as e:
        logger.error(f"❌ Bot initialization failed: {e}")
        logger.error("📝 Please check your TELEGRAM_BOT_TOKEN configuration in Render")
        return
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()

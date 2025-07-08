#!/usr/bin/env python3
"""
🚀 Subscriber_tracking Bot - Render Entry Point

This is the main entry point for the Subscriber_tracking bot on Render.
Render looks for main.py to start the application.
"""

import os
import logging
from subscriber_tracking_bot import SubscriberTrackingBot

# הגדרת logging לRender
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to start the Subscriber_tracking bot"""
    logger.info("🚀 Starting Subscriber_tracking Bot on Render...")
    
    # וידוא שיש טוקן
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token or token == '8127449182:AAFPRm1Vg9IC7NOD-x21VO5AZuYtoKTKWXU':
        logger.error("❌ TELEGRAM_BOT_TOKEN environment variable not set!")
        logger.error("Please configure it in your Render service settings.")
        return
    
    # יצירה והפעלה של הבוט
    try:
        bot = SubscriberTrackingBot()
        logger.info("✅ Bot initialized successfully")
        bot.run()
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()

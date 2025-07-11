# main.py (מותאם ל-Background Worker)
import os
import logging
import asyncio

# ודא שהייבוא תואם לשמות הקבצים שלך
from config import Config
from bot_logic import SubscriberTrackingBot

# הגדרת לוגינג
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    הפונקציה הראשית שמפעילה את הבוט.
    """
    # קבלת טוקן
    try:
        token = Config.validate_token()
    except ValueError as e:
        logger.critical(f"🚨 Configuration error: {e}")
        return

    # יצירת הבוט
    bot = SubscriberTrackingBot(token=token)

    logger.info("🚀 Starting bot as a background worker...")
    
    try:
        # הפעלת הבוט
        await bot.run_async()
        
        # השאר את התוכנית רצה לנצח
        await asyncio.Event().wait()
        
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        # כיבוי מבוקר
        logger.info("Shutting down...")
        await bot.stop_async()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"❌ A critical error caused the application to stop: {e}")

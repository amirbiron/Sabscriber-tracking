import os
import logging
import asyncio
from aiohttp import web

from config import Config
from bot_logic import SubscriberTrackingBot

# הגדרת לוגינג
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def web_server_handler(request):
    """עונה לבקשות GET כדי ש-Render ידע שהשירות פעיל."""
    return web.Response(text="Bot service is alive.")


async def main():
    """
    הפונקציה הראשית שמפעילה את הבוט ואת שרת הרקע באופן אסינכרוני.
    """
    # --- הוספת עיכוב של 15 שניות למניעת קונפליקט ב-Deploy ---
    logger.info("Starting up, waiting 15 seconds for old instance to shut down...")
    await asyncio.sleep(15)
    # -----------------------------------------------------------

    # קבלת טוקן
    try:
        token = Config.validate_token()
    except ValueError as e:
        logger.critical(f"🚨 Configuration error: {e}")
        return

    # יצירת הבוט
    bot = SubscriberTrackingBot(token=token)

    # הגדרת שרת ה-Web של aiohttp (נדרש עבור Web Service ב-Render)
    app = web.Application()
    app.router.add_get('/', web_server_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)

    logger.info(f"🚀 Starting bot and web server on port {port}...")
    
    try:
        # הפעלת הבוט ושרת הרקע במקביל
        await bot.run_async()
        await site.start()
        
        # השאר את התוכנית רצה לנצח
        await asyncio.Event().wait()
        
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        # כיבוי מבוקר
        logger.info("Shutting down...")
        await bot.stop_async()
        await runner.cleanup()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"❌ A critical error caused the application to stop: {e}")


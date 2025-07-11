# main.py (גרסה מינימלית לבדיקה)
import os
import logging
import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# הגדרת לוגינג
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# פונקציית start פשוטה
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
    await update.message.reply_text('היי! הבוט המינימלי עובד!')

async def main() -> None:
    """הפונקציה הראשית שמפעילה את הבוט המינימלי."""
    
    # קריאת הטוקן ישירות כאן
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    # יצירת האפליקציה
    app = Application.builder().token(token).build()

    # הוספת פקודת start בלבד
    app.add_handler(CommandHandler("start", start))

    logger.info("Starting minimal bot...")
    
    # הרצת הבוט
    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Minimal bot is polling.")
        # השאר את התוכנית רצה
        await asyncio.Event().wait()
    finally:
        # כיבוי מבוקר
        logger.info("Shutting down minimal bot.")
        if app.updater.running:
            await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())

main.py

#!/usr/bin/env python3 """ 🚀 Entry point for ReadLater Bot - Polling only """

import os import logging import requests from bot_logic import get_telegram_app

לוגים

logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s' ) logger = logging.getLogger(name)

def main(): logger.info("🚀 Starting ReadLater Bot...")

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

if name == "main": main()

---

bot_logic.py

import logging import os from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

הגדרת logger

logger = logging.getLogger(name) logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' )

Dummy logic - כאן אתה אמור להכניס את המחלקה ReadLaterBot שלך וכל הפונקציות (start, help וכו')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): logger.info("📩 /start command received") await update.message.reply_text("שלום! הבוט מוכן לפעולה ✨")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("השתמש ב-/start כדי להתחיל 🛠️")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.callback_query.answer("עוד לא הוגדר כפתור פעולה")

async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("קיבלת לחצן קבוע. בקרוב נוסיף פונקציות ✨")

async def saved_articles(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("(ריק) אין כתבות שמורות כרגע")

def get_telegram_app(): application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("saved", saved_articles))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyboard_buttons))
application.add_handler(CallbackQueryHandler(button_callback))

return application


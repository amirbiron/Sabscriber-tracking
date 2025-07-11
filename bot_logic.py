import logging
import sqlite3
import re
from datetime import datetime
from typing import Optional, List, Any

# Optional imports for OCR
try:
    from PIL import Image, ImageEnhance
    import pytesseract
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except (ImportError, Exception):
    OCR_AVAILABLE = False

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from db_manager import DatabaseManager

logger = logging.getLogger(__name__)

# Conversation states
ADD_SERVICE, ADD_AMOUNT, ADD_CURRENCY, ADD_DATE = range(4)

class SubscriberTrackingBot:
    """The main class for the Subscriber Tracking Bot."""

    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(self.token).build()
        self.scheduler = AsyncIOScheduler()
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.db.init_database()
        self.setup_handlers()

    # --- NEW ASYNC RUN/STOP METHODS (Corrected Order) ---
    async def run_async(self):
        """מפעיל את הבוט באופן אסינכרוני ולא חוסם."""
        await self.app.initialize()
        await self.app.start()  # <-- Step 1: Start the application
        if self.app.updater:
            await self.app.updater.start_polling() # <-- Step 2: Start polling for updates
        
        if self.scheduler.running:
             logger.info("Scheduler is already running.")
        else:
             self.scheduler.start()
             logger.info("Scheduler started.")
        logger.info("Bot has started polling asynchronously.")

    async def stop_async(self):
        """עוצר את הבוט באופן מבוקר."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped.")
        if self.app.updater:
            await self.app.updater.stop()
        await self.app.stop()
        logger.info("Bot has stopped.")
        
    def setup_handlers(self):
        """Register all command, message, and callback handlers."""
        add_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("add_subscription", self.add_subscription_start)],
            states={
                ADD_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_service)],
                ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_amount)],
                ADD_CURRENCY: [
                    CallbackQueryHandler(self.handle_currency_selection, pattern='^currency_'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_currency_text)
                ],
                ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_date)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_user=True
        )

        self.app.add_handler(add_conv_handler)
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("my_subs", self.my_subscriptions_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("upcoming", self.upcoming_payments_command))
        self.app.add_handler(CommandHandler("export", self.export_data_command))
        self.app.add_handler(MessageHandler(filters.Regex(r'^/delete_(\d+)$'), self.delete_subscription_command))
        
        # Note: 'Config.ENABLE_OCR' was not defined in the provided config.py.
        # You might need to add `ENABLE_OCR = os.getenv('ENABLE_OCR', 'false').lower() == 'true'`
        # to your config.py if you want to use this feature.
        # For now, I've commented it out to prevent errors.
        # if Config.ENABLE_OCR and OCR_AVAILABLE:
        #     self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_screenshot_ocr))
        
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown_text))
        
        logger.info("All handlers registered successfully.")

    # --- Core Command Handlers ---
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.db.ensure_user_settings(user.id)
        self.db.log_user_action(user.id, "start")
        welcome_text = f"👋 היי {user.first_name}!\nאני בוט למעקב אחר מנויים.\n\n" \
                       "התחל על ידי הוספת מנוי ראשון עם /add_subscription או הקלד /help למדריך."
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.db.log_user_action(update.effective_user.id, "help")
        help_text = """
📖 **מדריך למשתמש** 📖

**/add_subscription** - הוספת מנוי חדש.
**/my_subs** - הצגת כל המנויים הפעילים.
**/stats** - סטטיסטיקות ופילוח הוצאות.
**/upcoming** - תצוגת תשלומים קרובים.
**/export** - ייצוא הנתונים לקובץ CSV.
**/cancel** - ביטול פעולה נוכחית.
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def my_subscriptions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "my_subs")
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not subscriptions:
            await update.message.reply_text("לא מצאתי מנויים רשומים. הוסף אחד עם /add_subscription")
            return

        total_monthly = sum(sub['amount'] for sub in subscriptions if sub['currency'] == 'ILS')
        header = f"📄 **הנה המנויים שלך ({len(subscriptions)}):**\n\n**סה\"כ הוצאה חודשית (ב-ILS):** {total_monthly:.2f} ₪\n"
        
        subs_text = ""
        for sub in subscriptions:
            emoji = self.get_category_emoji(sub['category'])
            subs_text += (f"\n{emoji} **{sub['service_name']}**\n"
                          f"    💰 {sub['amount']:.2f} {sub['currency']} | 🗓️ ב-{sub['billing_day']} לחודש\n"
                          f"    `/delete_{sub['id']}`\n")
        
        keyboard = [[InlineKeyboardButton("➕ הוסף מנוי חדש", callback_data="add_new_sub")]]
        await update.message.reply_text(header + subs_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "view_stats")
        categories = self.db.get_stats_by_category(user_id)

        if not categories:
            await update.message.reply_text("אין נתונים להצגת סטטיסטיקות. הוסף מנויים תחילה.")
            return

        total_amount = sum(cat['total'] for cat in categories)
        stats_text = f"📊 **סטטיסטיקות לפי קטגוריה**\n\n**סה\"כ חודשי:** {total_amount:.2f} ₪\n"

        for cat in categories:
            emoji = self.get_category_emoji(cat['category'])
            percentage = (cat['total'] / total_amount * 100) if total_amount > 0 else 0
            stats_text += f"\n{emoji} **{cat['category'].title()}:** {cat['total']:.2f} ₪ ({percentage:.1f}%)"

        await update.message.reply_text(stats_text, parse_mode='Markdown')

    async def upcoming_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "view_upcoming")
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not subscriptions:
            await update.message.reply_text("אין מנויים פעילים.")
            return

        today = datetime.now().day
        upcoming_subs = []
        for sub in subscriptions:
            if sub['billing_day'] >= today:
                days_until = sub['billing_day'] - today
                upcoming_subs.append((days_until, sub))
        
        upcoming_subs.sort(key=lambda x: x[0])
        
        text = f"🗓️ **תשלומים קרובים (עד סוף החודש):**\n"
        if not upcoming_subs:
            text += "\nאין חיובים צפויים עד סוף החודש."
        else:
            for days, sub in upcoming_subs:
                when = "היום" if days == 0 else "מחר" if days == 1 else f"בעוד {days} ימים"
                text += f"\n- **{when} ({sub['billing_day']} לחודש):** {sub['service_name']} - {sub['amount']:.2f} {sub['currency']}"

        await update.message.reply_text(text)

    async def export_data_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # This command is not fully implemented in the provided code
        await update.message.reply_text("פיצ'ר הייצוא יפותח בהמשך.")
        pass

    # --- Add Subscription Conversation ---
    async def add_subscription_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.db.log_user_action(update.effective_user.id, "add_subscription_start")
        await update.message.reply_text(
            "נהדר! בוא נוסיף מנוי חדש.\n\n"
            "**מה שם השירות?** (למשל, Netflix, Spotify...)\n\n"
            "אפשר לבטל בכל רגע עם /cancel."
        )
        return ADD_SERVICE

    async def add_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        service_name = update.message.text.strip()
        context.user_data['service_name'] = service_name
        context.user_data['detected_category'] = self.detect_service_category(service_name)

        await update.message.reply_text(
            f"👍 שירות: **{service_name}**.\n\n"
            "**מה סכום החיוב החודשי?**"
        )
        return ADD_AMOUNT

    async def add_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            amount = float(re.sub(r'[^\d.]', '', update.message.text))
            context.user_data['amount'] = amount
            
            keyboard = [
                [InlineKeyboardButton("₪ שקל", callback_data="currency_ILS")],
                [InlineKeyboardButton("$ דולר", callback_data="currency_USD")],
                [InlineKeyboardButton("€ אירו", callback_data="currency_EUR")],
                [InlineKeyboardButton("אחר", callback_data="currency_other")]
            ]
            await update.message.reply_text(
                f"💰 סכום: **{amount}**. באיזה מטבע?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ADD_CURRENCY
        except (ValueError, TypeError):
            await update.message.reply_text("נראה שזה לא מספר חוקי. אנא הקלד רק את סכום החיוב:")
            return ADD_AMOUNT

    async def handle_currency_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        currency_code = query.data.split('_')[1]
        
        if currency_code == "other":
            await query.edit_message_text("בסדר, הקלד את סימון המטבע:")
            return ADD_CURRENCY

        context.user_data['currency'] = currency_code
        await query.edit_message_text(
            f"✅ מטבע: **{currency_code}**.\n\n"
            "**באיזה יום בחודש מתבצע החיוב?** (1-28)"
        )
        return ADD_DATE

    async def add_currency_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        currency = update.message.text.strip().upper()
        context.user_data['currency'] = currency
        await update.message.reply_text(
             f"✅ מטבע: **{currency}**.\n\n"
            "**באיזה יום בחודש מתבצע החיוב?** (1-28)"
        )
        return ADD_DATE

    async def add_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            day = int(update.message.text.strip())
            if not 1 <= day <= 28:
                await update.message.reply_text("יום החיוב חייב להיות בין 1 ל-28. נסה שוב:")
                return ADD_DATE

            user_id = update.effective_user.id
            ud = context.user_data
            self.db.add_subscription(
                user_id, ud['service_name'], ud['amount'], ud['currency'], day, ud['detected_category']
            )
            self.db.log_user_action(user_id, "add_subscription_finish")

            await update.message.reply_text(
                f"🎉 **המנוי נוסף בהצלחה.**\n"
                f"שירות: {ud['service_name']}\n"
                f"סכום: {ud['amount']} {ud['currency']}\n"
                f"יום חיוב: {day} בחודש"
            )
            ud.clear()
            return ConversationHandler.END
        except (ValueError, TypeError):
            await update.message.reply_text("הקלד יום בחודש (1-28):")
            return ADD_DATE

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("הפעולה בוטלה.")
        return ConversationHandler.END

    # --- Edit/Delete Handlers ---
    async def delete_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        sub_id = int(context.matches[0].group(1))
        
        sub = self.db.get_subscription_by_id(sub_id, user_id)
        if not sub:
            await update.message.reply_text("מנוי לא נמצא.")
            return

        text = f"האם למחוק את המנוי **{sub['service_name']}**?"
        keyboard = [[
            InlineKeyboardButton("✅ כן", callback_data=f"confirm_delete_{sub_id}"),
            InlineKeyboardButton("❌ לא", callback_data="cancel_delete")
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    # --- OCR Handler ---
    async def handle_screenshot_ocr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("פיצ'ר זיהוי תמונה עדיין בפיתוח.")

    # --- General Handlers ---
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.effective_user.id
        data = query.data

        if data.startswith("confirm_delete_"):
            sub_id = int(data.split('_')[2])
            sub = self.db.get_subscription_by_id(sub_id, user_id)
            if sub:
                self.db.delete_subscription(sub_id, user_id)
                await query.edit_message_text(f"🗑️ המנוי **{sub['service_name']}** נמחק.")
                self.db.log_user_action(user_id, f"delete_subscription_confirm_{sub_id}")
            else:
                await query.edit_message_text("המנוי כבר נמחק.")
        
        elif data == "cancel_delete":
            await query.edit_message_text("פעולת המחיקה בוטלה.")
        
        elif data == "add_new_sub":
            await query.edit_message_text("כדי להוסיף מנוי חדש, הקלד:\n/add_subscription")

    async def handle_unknown_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("לא הבנתי. נסה /help.")

    # --- Helper Methods ---
    def get_category_emoji(self, category: str) -> str:
        emoji_map = {
            'streaming': '📺', 'music': '🎵', 'productivity': '📈', 'cloud': '☁️',
            'software': '💻', 'gaming': '🎮', 'news': '📰', 'fitness': '🏋️‍♀️',
            'education': '🎓', 'communication': '💬', 'financial': '🏦', 'other': '📌'
        }
        return emoji_map.get(category, '📌')

    def detect_service_category(self, service_name: str) -> str:
        service_lower = service_name.lower()
        category_keywords = {
            'streaming': ['netflix', 'disney', 'amazon prime', 'hbo', 'hulu', 'apple tv', 'yes+', 'sting', 'cellcom tv'],
            'music': ['spotify', 'apple music', 'youtube music', 'deezer', 'tidal'],
            'productivity': ['office', 'microsoft 365', 'notion', 'slack', 'zoom', 'asana', 'trello'],
            'cloud': ['dropbox', 'google drive', 'icloud', 'one drive'],
            'software': ['adobe', 'photoshop', 'figma', 'canva', 'github', 'autocad'],
            'gaming': ['xbox', 'playstation', 'steam', 'nintendo'],
            'fitness': ['gym', 'strava', 'myfitnesspal']
        }
        for category, keywords in category_keywords.items():
            if any(keyword in service_lower for keyword in keywords):
                return category
        return 'other'

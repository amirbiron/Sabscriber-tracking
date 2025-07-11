#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 Subscriber_tracking Bot
בוט ניהול מנויים אישי חכם - מותאם ל-Render

Created by: Your Development Team
Version: 1.1.0 (Refactored)
Deployment: Render.com
"""

import logging
import sqlite3
import asyncio
import signal
import re
import os
import io
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any

# Optional imports handled with feature flags
try:
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except (ImportError, Exception):
    OCR_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- הגדרת logging בתחילת הקובץ ---
# Render's environment provides stdout logging, which is sufficient.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- Configuration Class ---
class Config:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'subscriber_tracking.db') # Use local file for easier dev
    NOTIFICATION_HOUR = int(os.getenv('NOTIFICATION_HOUR', 9))
    NOTIFICATION_MINUTE = int(os.getenv('NOTIFICATION_MINUTE', 0))
    ENABLE_OCR = os.getenv('ENABLE_OCR', 'true').lower() == 'true' and OCR_AVAILABLE
    DEMO_SAVINGS = float(os.getenv('DEMO_SAVINGS', 2847.50))

    COMMON_SERVICES = [
        'Netflix', 'Spotify', 'ChatGPT Plus', 'YouTube Premium',
        'Amazon Prime', 'Disney+', 'Apple Music', 'Office 365',
        'Adobe Creative Cloud', 'Dropbox', 'iCloud', 'HBO Max',
        'Zoom Pro', 'Slack', 'Notion', 'Figma', 'Canva Pro'
    ]

    @classmethod
    def validate_token(cls):
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")
        return cls.TELEGRAM_BOT_TOKEN

# --- Conversation States ---
ADD_SERVICE, ADD_AMOUNT, ADD_CURRENCY, ADD_DATE = range(4)
EDIT_CHOICE, EDIT_VALUE = range(2)


# --- Database Manager Class (Refactored) ---
class DatabaseManager:
    """Handles all database operations for the bot."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        logger.info(f"DatabaseManager initialized with path: {self.db_path}")

    def _execute(self, query: str, params: tuple = (), fetch: str = None):
        """Helper function to connect, execute, and close."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row # Makes fetching columns by name easy
                cursor = conn.cursor()
                cursor.execute(query, params)
                if fetch == 'one':
                    return cursor.fetchone()
                if fetch == 'all':
                    return cursor.fetchall()
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
            return None # Or raise a custom exception

    def init_database(self):
        """Initializes all tables in the database if they don't exist."""
        # Create tables using a list of queries for cleanliness
        create_table_queries = [
            '''CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, service_name TEXT NOT NULL,
                amount REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'ILS', billing_day INTEGER NOT NULL,
                billing_cycle TEXT DEFAULT 'monthly', category TEXT DEFAULT 'other', notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1, auto_detected BOOLEAN DEFAULT 0
            )''',
            '''CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY, timezone TEXT DEFAULT 'Asia/Jerusalem',
                notification_time TEXT DEFAULT '09:00', language TEXT DEFAULT 'he',
                currency_preference TEXT DEFAULT 'ILS', weekly_summary BOOLEAN DEFAULT 1,
                smart_suggestions BOOLEAN DEFAULT 1
            )''',
            '''CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                action TEXT NOT NULL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]
        for query in create_table_queries:
            self._execute(query)
        logger.info("Database initialized successfully.")

    def add_subscription(self, user_id: int, service_name: str, amount: float, currency: str, billing_day: int, category: str):
        query = '''INSERT INTO subscriptions (user_id, service_name, amount, currency, billing_day, category)
                   VALUES (?, ?, ?, ?, ?, ?)'''
        return self._execute(query, (user_id, service_name, amount, currency, billing_day, category))

    def get_user_subscriptions(self, user_id: int) -> List[sqlite3.Row]:
        query = 'SELECT * FROM subscriptions WHERE user_id = ? AND is_active = 1 ORDER BY billing_day ASC'
        return self._execute(query, (user_id,), fetch='all')

    def get_subscription_by_id(self, sub_id: int, user_id: int) -> Optional[sqlite3.Row]:
        query = 'SELECT * FROM subscriptions WHERE id = ? AND user_id = ? AND is_active = 1'
        return self._execute(query, (sub_id, user_id), fetch='one')

    def delete_subscription(self, sub_id: int, user_id: int):
        # We perform a "soft delete" by setting is_active to 0. This preserves data.
        query = 'UPDATE subscriptions SET is_active = 0 WHERE id = ? AND user_id = ?'
        self._execute(query, (sub_id, user_id))
        logger.info(f"Soft deleted subscription {sub_id} for user {user_id}")

    def update_subscription(self, sub_id: int, user_id: int, field: str, value: Any):
        # Note: Be careful with this pattern to avoid SQL injection if field names come from user input.
        # Here, field names are controlled by our code, so it's safe.
        query = f'UPDATE subscriptions SET {field} = ?, last_modified = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?'
        self._execute(query, (value, sub_id, user_id))

    def get_stats_by_category(self, user_id: int) -> List[sqlite3.Row]:
        query = '''SELECT category, COUNT(*) as count, SUM(amount) as total
                   FROM subscriptions WHERE user_id = ? AND is_active = 1
                   GROUP BY category ORDER BY total DESC'''
        return self._execute(query, (user_id,), fetch='all')

    def log_user_action(self, user_id: int, action: str):
        query = 'INSERT INTO usage_stats (user_id, action) VALUES (?, ?)'
        self._execute(query, (user_id, action))

    def ensure_user_settings(self, user_id: int):
        if not self._execute('SELECT user_id FROM user_settings WHERE user_id = ?', (user_id,), fetch='one'):
            self._execute('INSERT INTO user_settings (user_id) VALUES (?)', (user_id,))
            logger.info(f"Created default settings for new user {user_id}")
    
    def get_user_settings(self, user_id: int) -> Optional[sqlite3.Row]:
        self.ensure_user_settings(user_id)
        return self._execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,), fetch='one')

# --- Main Bot Class ---
class SubscriberTrackingBot:
    """The main class for the Subscriber Tracking Bot."""

    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(self.token).build()
        self.scheduler = AsyncIOScheduler()
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.db.init_database()

    def setup_handlers(self):
        """Register all command, message, and callback handlers."""
        # Conversation handler for adding a new subscription
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

        # Standard command handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("my_subs", self.my_subscriptions_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("analytics", self.analytics_command))
        self.app.add_handler(CommandHandler("upcoming", self.upcoming_payments_command))
        self.app.add_handler(CommandHandler("export", self.export_data_command))
        self.app.add_handler(CommandHandler("settings", self.settings_command))
        
        # Regex handlers for specific command patterns
        self.app.add_handler(MessageHandler(filters.Regex(r'^/edit_(\d+)$'), self.edit_subscription_command))
        self.app.add_handler(MessageHandler(filters.Regex(r'^/delete_(\d+)$'), self.delete_subscription_command))

        # OCR handler for photos
        if Config.ENABLE_OCR:
            self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_screenshot_ocr))
        
        # General callback handler for all other inline buttons
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

        # Fallback for any unrecognized text
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown_text))
        
        logger.info("All handlers registered successfully.")

    # --- Core Command Handlers ---
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.db.ensure_user_settings(user.id)
        self.db.log_user_action(user.id, "start")
        welcome_text = f"👋 היי {user.first_name}!\nאני בוט למעקב אחר מנויים.\n\n" \
                       "אני יכול לעזור לך:\n" \
                       "✅ לעקוב אחרי כל ההוצאות החודשיות\n" \
                       "📊 לקבל סטטיסטיקות ותובנות\n" \
                       "🗓️ לקבל תזכורות לפני חיוב\n\n" \
                       "התחל על ידי הוספת מנוי ראשון עם /add_subscription או הקלד /help למדריך."
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.db.log_user_action(update.effective_user.id, "help")
        help_text = """
📖 **מדריך למשתמש** 📖

**/add_subscription** - הוספת מנוי חדש בתהליך מודרך.
**/my_subs** - הצגת כל המנויים הפעילים שלך.
**/stats** - סטטיסטיקות ופילוח הוצאות.
**/analytics** - ניתוח מתקדם והמלצות לחיסכון.
**/upcoming** - תצוגת תשלומים קרובים (ב-30 הימים הבאים).
**/export** - ייצוא כל הנתונים שלך לקובץ CSV.
**/settings** - שינוי הגדרות אישיות כמו שעת התראה.
**/cancel** - ביטול הפעולה הנוכחית (למשל, באמצע הוספת מנוי).

💡 **טיפ:** ניתן גם לשלוח צילום מסך של חיוב, ואנסה לזהות את הפרטים אוטומטית!
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def my_subscriptions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "my_subs")
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not subscriptions:
            await update.message.reply_text("לא מצאתי מנויים רשומים. הוסף אחד עם /add_subscription")
            return

        total_monthly = sum(sub['amount'] for sub in subscriptions)
        header = f"📄 **הנה המנויים שלך ({len(subscriptions)}):**\n\n**סה\"כ הוצאה חודשית:** {total_monthly:.2f} ₪\n"
        
        subs_text = ""
        for sub in subscriptions:
            emoji = self.get_category_emoji(sub['category'])
            subs_text += (f"\n{emoji} **{sub['service_name']}**\n"
                          f"    💰 {sub['amount']:.2f} {sub['currency']} | 🗓️ ב-{sub['billing_day']} לחודש\n"
                          f"    `/edit_{sub['id']}` | `/delete_{sub['id']}`\n")
        
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

    async def analytics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📈 פיצ'ר ניתוח מתקדם והמלצות חיסכון יתווסף בקרוב!")

    async def upcoming_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "view_upcoming")
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not subscriptions:
            await update.message.reply_text("אין מנויים פעילים לתצוגת תשלומים קרובים.")
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
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "export_data")
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not subscriptions:
            await update.message.reply_text("אין נתונים לייצוא.")
            return
        
        # Create CSV in memory
        output = io.StringIO()
        output.write("שירות,סכום,מטבע,יום_חיוב,קטגוריה,הערות,תאריך_יצירה\n")
        for sub in subscriptions:
            notes = sub['notes'] or ""
            output.write(f'"{sub["service_name"]}",{sub["amount"]},"{sub["currency"]}",{sub["billing_day"]},'
                         f'"{sub["category"]}","{notes}","{sub["created_at"]}"\n')
        
        # Seek to the beginning of the stream
        output.seek(0)
        
        # Send as a file
        await update.message.reply_document(
            document=InputFile(io.BytesIO(output.getvalue().encode('utf-8')), 'subscriptions.csv'),
            caption="הנה הנתונים שלך בקובץ CSV."
        )

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        settings = self.db.get_user_settings(user_id)
        text = f"""
⚙️ **הגדרות**

שעת התראה יומית: {settings['notification_time']}
שפת ממשק: {settings['language']}

פיצ'רים נוספים יתווספו בעתיד.
        """
        await update.message.reply_text(text)


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
            "**מה סכום החיוב החודשי?** (הקלד רק את המספר)"
        )
        return ADD_AMOUNT

    async def add_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            amount = float(re.sub(r'[^\d.]', '', update.message.text))
            if amount <= 0: raise ValueError
            context.user_data['amount'] = amount
            
            keyboard = [
                [InlineKeyboardButton("₪ שקל", callback_data="currency_ILS")],
                [InlineKeyboardButton("$ דולר", callback_data="currency_USD")],
                [InlineKeyboardButton("€ אירו", callback_data="currency_EUR")],
                [InlineKeyboardButton("אחר (טקסט)", callback_data="currency_other")]
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
            await query.edit_message_text("בסדר, הקלד את סימון המטבע (לדוגמה: GBP):")
            return ADD_CURRENCY

        context.user_data['currency'] = currency_code
        await query.edit_message_text(
            f"✅ מטבע: **{currency_code}**.\n\n"
            "**באיזה יום בחודש מתבצע החיוב?** (מספר בין 1-28)"
        )
        return ADD_DATE

    async def add_currency_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        currency = update.message.text.strip().upper()
        context.user_data['currency'] = currency
        await update.message.reply_text(
             f"✅ מטבע: **{currency}**.\n\n"
            "**באיזה יום בחודש מתבצע החיוב?** (מספר בין 1-28)"
        )
        return ADD_DATE

    async def add_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            day = int(update.message.text.strip())
            if not 1 <= day <= 28:
                await update.message.reply_text("יום החיוב חייב להיות בין 1 ל-28. נסה שוב:")
                return ADD_DATE

            # All data collected, save to DB
            user_id = update.effective_user.id
            ud = context.user_data
            self.db.add_subscription(
                user_id, ud['service_name'], ud['amount'], ud['currency'], day, ud['detected_category']
            )
            self.db.log_user_action(user_id, "add_subscription_finish")

            await update.message.reply_text(
                f"🎉 **מעולה! המנוי נוסף בהצלחה.**\n\n"
                f"שירות: {ud['service_name']}\n"
                f"סכום: {ud['amount']} {ud['currency']}\n"
                f"יום חיוב: {day} בחודש\n\n"
                "אזכיר לך לפני החיוב הבא. צפה בכל המנויים עם /my_subs."
            )
            ud.clear()
            return ConversationHandler.END
        except (ValueError, TypeError):
            await update.message.reply_text("זה לא נראה כמספר תקין. הקלד יום בחודש (1-28):")
            return ADD_DATE

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("הפעולה בוטלה. לחץ /start כדי להתחיל מחדש.")
        return ConversationHandler.END


    # --- Edit/Delete Handlers ---
    async def edit_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        sub_id = int(context.matches[0].group(1))
        # This will be implemented in a future version with another conversation handler.
        await update.message.reply_text(f"פיצ'ר עריכת מנוי #{sub_id} יפותח בהמשך.")

    async def delete_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        sub_id = int(context.matches[0].group(1))
        
        sub = self.db.get_subscription_by_id(sub_id, user_id)
        if not sub:
            await update.message.reply_text("מנוי לא נמצא או שאין לך הרשאה למחוק אותו.")
            return

        text = f"אתה בטוח שברצונך למחוק את המנוי **{sub['service_name']}** ({sub['amount']} {sub['currency']})?"
        keyboard = [
            [
                InlineKeyboardButton("✅ כן, מחק", callback_data=f"confirm_delete_{sub_id}"),
                InlineKeyboardButton("❌ לא, בטל", callback_data="cancel_delete")
            ]
        ]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    # --- OCR Handler ---
    async def handle_screenshot_ocr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        processing_msg = await update.message.reply_text("🖼️ קיבלתי את התמונה, מנסה לזהות פרטים...")
        try:
            photo_file = await update.message.photo[-1].get_file()
            image_bytes = io.BytesIO()
            await photo_file.download_to_memory(image_bytes)
            image_bytes.seek(0)
            
            image = Image.open(image_bytes).convert('L') # Grayscale
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0) # Increase contrast
            
            text = pytesseract.image_to_string(image, lang='heb+eng')
            # For now, we just show the text. Parsing logic can be added here.
            await processing_msg.edit_text(f"**טקסט שזוהה מהתמונה:**\n\n`{text[:500]}`\n\nפיצ'ר הזיהוי האוטומטי עדיין בפיתוח. בינתיים, אפשר להשתמש ב-/add_subscription.", parse_mode='Markdown')

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            await processing_msg.edit_text("שגיאה בעיבוד התמונה. אנא נסה שוב או השתמש ב-/add_subscription.")

    # --- General Handlers ---
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """A general handler for many inline buttons."""
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
                await query.edit_message_text("המנוי כבר נמחק או שלא ניתן היה למצוא אותו.")
        
        elif data == "cancel_delete":
            await query.edit_message_text("פעולת המחיקה בוטלה.")
        
        elif data == "add_new_sub":
            await query.edit_message_text("כדי להוסיף מנוי חדש, הקלד את הפקודה:\n/add_subscription")

    async def handle_unknown_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("לא הבנתי את הפקודה. 🤔\nנסה /help כדי לראות מה אני יודע לעשות.")

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

    # --- Bot Lifecycle ---
    def run(self):
        """Set up handlers and run the bot."""
        self.setup_handlers()
        
        if self.scheduler:
            # You can add scheduled jobs here, e.g., for daily reminders
            # self.scheduler.add_job(...)
            self.scheduler.start()
            logger.info("Scheduler started.")

        logger.info("Bot is starting to poll...")
        self.app.run_polling()


def main():
    """Main function to setup and run the bot."""
    try:
        token = Config.validate_token()
        bot = SubscriberTrackingBot(token)
        bot.run()
    except ValueError as e:
        logger.critical(f"FATAL: Configuration error - {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"FATAL: An unexpected error occurred: {e}")
        sys.exit(1)

# --- Entry Point ---
if __name__ == "__main__":
    main()


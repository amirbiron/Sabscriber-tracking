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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ReplyKeyboardMarkup, KeyboardButton
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

    def get_main_menu_keyboard(self):
        """מחזיר את המקלדת הראשית עם כפתורים קבועים"""
        keyboard = [
            [KeyboardButton("➕ הוסף מנוי חדש"), KeyboardButton("📋 המנויים שלי")],
            [KeyboardButton("📊 סטטיסטיקות"), KeyboardButton("🗓️ תשלומים קרובים")],
            [KeyboardButton("⚙️ הגדרות"), KeyboardButton("❓ עזרה")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)

    def get_inline_main_menu(self):
        """מחזיר כפתורי תפריט ראשי כ-inline"""
        keyboard = [
            [InlineKeyboardButton("➕ הוסף מנוי חדש", callback_data="add_new_sub")],
            [InlineKeyboardButton("📋 המנויים שלי", callback_data="my_subs"), 
             InlineKeyboardButton("📊 סטטיסטיקות", callback_data="stats")],
            [InlineKeyboardButton("🗓️ תשלומים קרובים", callback_data="upcoming"),
             InlineKeyboardButton("⚙️ הגדרות", callback_data="settings")],
            [InlineKeyboardButton("❓ עזרה", callback_data="help")]
        ]
        return InlineKeyboardMarkup(keyboard)

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
            entry_points=[
                CommandHandler("add_subscription", self.add_subscription_start),
                CallbackQueryHandler(self.add_subscription_start, pattern='^add_new_sub$')
            ],
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
        self.app.add_handler(CommandHandler("settings", self.settings_command))
        self.app.add_handler(MessageHandler(filters.Regex(r'^/delete_(\d+)$'), self.delete_subscription_command))
        
        # מטפל בכפתורי המקלדת הקבועה
        self.app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^➕ הוסף מנוי חדש$'), self.handle_add_subscription_button))
        self.app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^📋 המנויים שלי$'), self.handle_my_subs_button))
        self.app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^📊 סטטיסטיקות$'), self.handle_stats_button))
        self.app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^🗓️ תשלומים קרובים$'), self.handle_upcoming_button))
        self.app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^⚙️ הגדרות$'), self.handle_settings_button))
        self.app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^❓ עזרה$'), self.handle_help_button))
        
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown_text))
        
        logger.info("All handlers registered successfully.")

    # --- Button Handlers ---
    async def handle_add_subscription_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.add_subscription_start(update, context)

    async def handle_my_subs_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.my_subscriptions_command(update, context)

    async def handle_stats_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.stats_command(update, context)

    async def handle_upcoming_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.upcoming_payments_command(update, context)

    async def handle_settings_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.settings_command(update, context)

    async def handle_help_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.help_command(update, context)

    # --- Core Command Handlers ---
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.db.ensure_user_settings(user.id)
        self.db.log_user_action(user.id, "start")
        
        welcome_text = f"""🎉 **ברוכים הבאים לבוט מעקב המנויים המשודרג!**

👋 שלום {user.first_name}!

🔥 **מה חדש בגרסה המשודרגת:**
• 🎯 כפתורים נוחים במקום פקודות
• 📊 סטטיסטיקות מפורטות ומתקדמות
• 🗓️ תזכורות חכמות לתשלומים
• ⚙️ הגדרות מותאמות אישית
• 💡 ממשק נעים ואינטואיטיבי

📱 **איך להתחיל:**
לחץ על "➕ הוסף מנוי חדש" כדי להוסיף את המנוי הראשון שלך!

כל הכפתורים זמינים בתפריט למטה 👇"""
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.db.log_user_action(update.effective_user.id, "help")
        help_text = """
🆘 **מדריך מלא למשתמש** 🆘

🔹 **תפריט ראשי:**
• ➕ **הוסף מנוי חדש** - להוספת מנוי חדש במספר לחיצות
• 📋 **המנויים שלי** - הצגת כל המנויים שלך עם אפשרות עריכה
• 📊 **סטטיסטיקות** - ניתוח הוצאות מפורט לפי קטגוריות
• 🗓️ **תשלומים קרובים** - כל החיובים הקרובים עד סוף החודש
• ⚙️ **הגדרות** - התאמה אישית של הבוט
• ❓ **עזרה** - המדריך הזה

🎯 **טיפים לשימוש:**
• השתמש בכפתורים במקום להקליד
• כל הפעולות נגישות מהתפריט הראשי
• הבוט זוכר את כל המנויים שלך
• קבל התראות על תשלומים קרובים

💡 **פקודות מיוחדות:**
• `/cancel` - לביטול פעולה נוכחית
• `/export` - לייצוא הנתונים
• `/delete_X` - למחיקת מנוי מספר X

🚀 **התחל עכשיו!**
לחץ על "➕ הוסף מנוי חדש" כדי להתחיל!
"""
        
        keyboard = [[InlineKeyboardButton("🔙 חזרה לתפריט ראשי", callback_data="main_menu")]]
        await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def my_subscriptions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "my_subs")
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not subscriptions:
            empty_text = """📋 **אין מנויים פעילים**

🎯 **התחל עכשיו:**
לחץ על "➕ הוסף מנוי חדש" כדי להוסיף את המנוי הראשון שלך!

💡 **למה כדאי לך לעקוב אחר המנויים:**
• 💰 שמור כסף על ידי מעקב אחר ההוצאות
• 📅 קבל תזכורות לפני חיובים
• 📊 ראה לאן הכסף הולך
• 🎯 נהל טוב יותר את התקציב שלך"""
            
            keyboard = [[InlineKeyboardButton("➕ הוסף מנוי ראשון", callback_data="add_new_sub")]]
            await update.message.reply_text(empty_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # חישובי סטטיסטיקה
        total_monthly_ils = sum(sub['amount'] for sub in subscriptions if sub['currency'] == 'ILS')
        total_monthly_usd = sum(sub['amount'] for sub in subscriptions if sub['currency'] == 'USD')
        total_monthly_eur = sum(sub['amount'] for sub in subscriptions if sub['currency'] == 'EUR')
        
        # כותרת עם סטטיסטיקות
        header = f"""📋 **המנויים שלך ({len(subscriptions)} מנויים פעילים)**

💰 **סיכום הוצאות חודשיות:**"""
        
        if total_monthly_ils > 0:
            header += f"\n• ₪ {total_monthly_ils:.2f} שקלים"
        if total_monthly_usd > 0:
            header += f"\n• $ {total_monthly_usd:.2f} דולרים"
        if total_monthly_eur > 0:
            header += f"\n• € {total_monthly_eur:.2f} אירו"
        
        header += f"\n• 📅 **הוצאה שנתית משוערת:** ₪ {total_monthly_ils * 12:.2f}"
        header += "\n" + "─" * 30 + "\n"
        
        # רשימת מנויים מעוצבת
        subs_text = ""
        for i, sub in enumerate(subscriptions, 1):
            emoji = self.get_category_emoji(sub['category'])
            next_payment = self.get_next_payment_date(sub['billing_day'])
            
            subs_text += f"""
{emoji} **{i}. {sub['service_name']}**
   💰 {sub['amount']:.2f} {sub['currency']} | 🗓️ {sub['billing_day']} לחודש
   📅 תשלום הבא: {next_payment}
   🗑️ `/delete_{sub['id']}` למחיקה
"""
        
        # כפתורי פעולה
        keyboard = [
            [InlineKeyboardButton("➕ הוסף מנוי נוסף", callback_data="add_new_sub")],
            [InlineKeyboardButton("📊 צפה בסטטיסטיקות", callback_data="stats"),
             InlineKeyboardButton("🗓️ תשלומים קרובים", callback_data="upcoming")],
            [InlineKeyboardButton("⚙️ הגדרות", callback_data="settings")]
        ]
        
        full_text = header + subs_text
        await update.message.reply_text(full_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    def get_next_payment_date(self, billing_day: int) -> str:
        """מחזיר את תאריך התשלום הבא"""
        from datetime import datetime, timedelta
        import calendar
        
        today = datetime.now()
        current_month = today.month
        current_year = today.year
        
        # אם התאריך עדיין לא עבר החודש
        if billing_day > today.day:
            return f"{billing_day}/{current_month}/{current_year}"
        else:
            # חישוב החודש הבא
            if current_month == 12:
                next_month = 1
                next_year = current_year + 1
            else:
                next_month = current_month + 1
                next_year = current_year
            
            return f"{billing_day}/{next_month}/{next_year}"
        
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "view_stats")
        categories = self.db.get_stats_by_category(user_id)
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not categories:
            no_data_text = """📊 **אין נתונים לסטטיסטיקות**

🎯 **התחל לעקוב אחר המנויים שלך:**
הוסף מנויים כדי לראות ניתוח מפורט של ההוצאות שלך!

💡 **מה תקבל בסטטיסטיקות:**
• 📈 פילוח הוצאות לפי קטגוריות
• 💰 חישוב הוצאות חודשיות ושנתיות
• 📊 גרפים ואחוזים
• 🎯 המלצות לחיסכון"""
            
            keyboard = [[InlineKeyboardButton("➕ הוסף מנוי ראשון", callback_data="add_new_sub")]]
            await update.message.reply_text(no_data_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            return

        total_amount = sum(cat['total'] for cat in categories)
        stats_text = f"""📊 **סטטיסטיקות מפורטות**

💰 **סיכום כספי:**
• 🗓️ **סה"כ חודשי:** ₪ {total_amount:.2f}
• 📅 **סה"כ שנתי:** ₪ {total_amount * 12:.2f}
• 📈 **ממוצע למנוי:** ₪ {total_amount / len(subscriptions):.2f}

📊 **פילוח לפי קטגוריות:**
"""

        # יצירת גרף עמודות פשוט
        for cat in categories:
            emoji = self.get_category_emoji(cat['category'])
            percentage = (cat['total'] / total_amount * 100) if total_amount > 0 else 0
            
            # יצירת "עמודה" ויזואלית
            bar_length = int(percentage / 10)  # כל 10% = תו אחד
            bar = "█" * bar_length + "░" * (10 - bar_length)
            
            stats_text += f"""
{emoji} **{cat['category'].title()}**
   {bar} {percentage:.1f}%
   💰 ₪ {cat['total']:.2f} ({cat['count']} מנויים)
"""

        # המלצות חכמות
        if total_amount > 200:
            stats_text += f"""
💡 **המלצות חכמות:**
• 🎯 ההוצאה החודשית שלך גבוהה - שקול לבטל מנויים לא נחוצים
• 📋 עבור על המנויים שלך ובדוק אילו מהם אתה באמת משתמש
• 💰 חיסכון של ₪ 50 לחודש = ₪ 600 לשנה!
"""

        keyboard = [
            [InlineKeyboardButton("📋 צפה במנויים", callback_data="my_subs")],
            [InlineKeyboardButton("🗓️ תשלומים קרובים", callback_data="upcoming")],
            [InlineKeyboardButton("⚙️ הגדרות", callback_data="settings")]
        ]

        await update.message.reply_text(stats_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def upcoming_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "view_upcoming")
        subscriptions = self.db.get_user_subscriptions(user_id)

        if not subscriptions:
            no_subs_text = """🗓️ **אין תשלומים קרובים**

🎯 **התחל לעקוב אחר התשלומים שלך:**
הוסף מנויים כדי לקבל תזכורות חכמות על תשלומים קרובים!

💡 **יתרונות מעקב תשלומים:**
• 🔔 תזכורות לפני חיובים
• 💰 מניעת חיובים לא צפויים
• 📊 תכנון תקציב טוב יותר
• 🎯 שליטה מלאה על ההוצאות"""
            
            keyboard = [[InlineKeyboardButton("➕ הוסף מנוי ראשון", callback_data="add_new_sub")]]
            await update.message.reply_text(no_subs_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            return

        today = datetime.now().day
        current_month = datetime.now().month
        
        # תשלומים החודש
        this_month_payments = []
        next_month_payments = []
        
        for sub in subscriptions:
            if sub['billing_day'] >= today:
                days_until = sub['billing_day'] - today
                this_month_payments.append((days_until, sub))
            else:
                # תשלום בחודש הבא
                next_month_payments.append(sub)
        
        this_month_payments.sort(key=lambda x: x[0])
        
        text = f"""🗓️ **תשלומים קרובים**

📅 **עד סוף החודש ({len(this_month_payments)} תשלומים):**
"""
        
        if not this_month_payments:
            text += "✅ אין תשלומים נוספים החודש!\n"
        else:
            total_this_month = 0
            for days, sub in this_month_payments:
                emoji = self.get_category_emoji(sub['category'])
                if days == 0:
                    when = "🚨 **היום!**"
                    urgency = "🔴"
                elif days == 1:
                    when = "⚠️ **מחר**"
                    urgency = "🟡"
                elif days <= 3:
                    when = f"📅 **בעוד {days} ימים**"
                    urgency = "🟢"
                else:
                    when = f"📅 **בעוד {days} ימים**"
                    urgency = "🔵"
                
                text += f"""
{urgency} {emoji} {when}
   💰 {sub['service_name']} - {sub['amount']:.2f} {sub['currency']}
   📊 {sub['billing_day']} לחודש
"""
                if sub['currency'] == 'ILS':
                    total_this_month += sub['amount']
            
            if total_this_month > 0:
                text += f"\n💰 **סה\"כ עד סוף החודש:** ₪ {total_this_month:.2f}"

        # תשלומים בחודש הבא
        if next_month_payments:
            text += f"\n\n📅 **בחודש הבא ({len(next_month_payments)} תשלומים):**\n"
            total_next_month = 0
            for sub in next_month_payments:
                emoji = self.get_category_emoji(sub['category'])
                text += f"• {emoji} {sub['service_name']} - {sub['amount']:.2f} {sub['currency']} (יום {sub['billing_day']})\n"
                if sub['currency'] == 'ILS':
                    total_next_month += sub['amount']
            
            if total_next_month > 0:
                text += f"\n💰 **סה\"כ בחודש הבא:** ₪ {total_next_month:.2f}"

        keyboard = [
            [InlineKeyboardButton("📋 צפה בכל המנויים", callback_data="my_subs")],
            [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="stats")],
            [InlineKeyboardButton("⚙️ הגדרות תזכורות", callback_data="settings")]
        ]

        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """תפריט הגדרות מתקדם"""
        user_id = update.effective_user.id
        self.db.log_user_action(user_id, "settings")
        
        settings_text = """⚙️ **הגדרות מתקדמות**

🔧 **התאם את הבוט לצרכים שלך:**

🔔 **תזכורות:**
• קבל התראות לפני תשלומים
• הגדר כמה ימים מראש להתריע
• בחר באילו מנויים לקבל התראות

📊 **הצגה:**
• מטבע ברירת מחדל
• פורמט תאריכים
• שפת הממשק

🎯 **תכנון תקציב:**
• הגדר מגבלת הוצאות חודשית
• קבל התראות על חריגה מהתקציב
• עקוב אחר מגמות הוצאות

💡 **אוטומציה:**
• זיהוי אוטומטי של קטגוריות
• המלצות על מנויים לביטול
• ניתוח דפוסי הוצאות"""
        
        keyboard = [
            [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_notifications")],
            [InlineKeyboardButton("💰 מטבע ברירת מחדל", callback_data="settings_currency")],
            [InlineKeyboardButton("📊 תקציב חודשי", callback_data="settings_budget")],
            [InlineKeyboardButton("📤 ייצוא נתונים", callback_data="export_data")],
            [InlineKeyboardButton("🔙 תפריט ראשי", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(settings_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def export_data_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ייצוא נתונים לקובץ CSV"""
        user_id = update.effective_user.id
        subscriptions = self.db.get_user_subscriptions(user_id)
        
        if not subscriptions:
            await update.message.reply_text("אין נתונים לייצוא. הוסף מנויים תחילה.")
            return
        
        # יצירת תוכן CSV
        csv_content = "שם השירות,סכום,מטבע,יום חיוב,קטגוריה,תאריך הוספה\n"
        for sub in subscriptions:
            csv_content += f"{sub['service_name']},{sub['amount']},{sub['currency']},{sub['billing_day']},{sub['category']},{sub.get('created_at', 'N/A')}\n"
        
        # שמירת קובץ זמני
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            await update.message.reply_document(
                document=open(temp_path, 'rb'),
                filename=f"my_subscriptions_{datetime.now().strftime('%Y%m%d')}.csv",
                caption="📤 **קובץ המנויים שלך מוכן!**\n\nהקובץ כולל את כל המנויים שלך בפורמט CSV."
            )
        finally:
            os.unlink(temp_path)  # מחיקת הקובץ הזמני

    # --- Add Subscription Conversation ---
    async def add_subscription_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.db.log_user_action(update.effective_user.id, "add_subscription_start")
        
        # אם זה callback query
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                """🎯 **הוספת מנוי חדש**

📝 **שלב 1 מתוך 4: שם השירות**

איך קוראים לשירות? (לדוגמה: Netflix, Spotify, Office 365)

💡 **טיפים:**
• הקלד את השם המלא של השירות
• הבוט יזהה אוטומטי את הקטגוריה
• אפשר לבטל בכל שלב עם /cancel
""",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                """🎯 **הוספת מנוי חדש**

📝 **שלב 1 מתוך 4: שם השירות**

איך קוראים לשירות? (לדוגמה: Netflix, Spotify, Office 365)

💡 **טיפים:**
• הקלד את השם המלא של השירות
• הבוט יזהה אוטומטי את הקטגוריה
• אפשר לבטל בכל שלב עם /cancel
""",
                parse_mode='Markdown'
            )
        return ADD_SERVICE

    async def add_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        service_name = update.message.text.strip()
        context.user_data['service_name'] = service_name
        detected_category = self.detect_service_category(service_name)
        context.user_data['detected_category'] = detected_category
        
        category_emoji = self.get_category_emoji(detected_category)
        category_name = detected_category.title()

        await update.message.reply_text(
            f"""✅ **שירות נשמר:** {service_name}
{category_emoji} **קטגוריה זוהתה:** {category_name}

📝 **שלב 2 מתוך 4: סכום החיוב**

כמה אתה משלם בחודש? (הקלד רק את המספר)

💡 **דוגמאות:**
• 39.90
• 15
• 120.5

אפשר לבטל עם /cancel
""",
            parse_mode='Markdown'
        )
        return ADD_AMOUNT

    async def add_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            amount_text = update.message.text.strip()
            # ניקוי הטקסט ממספרים שאינם רלוונטיים
            amount = float(re.sub(r'[^\d.,]', '', amount_text).replace(',', '.'))
            
            if amount <= 0:
                await update.message.reply_text("❌ הסכום חייב להיות חיובי. נסה שוב:")
                return ADD_AMOUNT
                
            context.user_data['amount'] = amount
            
            keyboard = [
                [InlineKeyboardButton("₪ שקל ישראלי (ILS)", callback_data="currency_ILS")],
                [InlineKeyboardButton("$ דולר אמריקאי (USD)", callback_data="currency_USD")],
                [InlineKeyboardButton("€ יורו (EUR)", callback_data="currency_EUR")],
                [InlineKeyboardButton("💱 מטבע אחר", callback_data="currency_other")]
            ]
            
            await update.message.reply_text(
                f"""💰 **סכום נשמר:** {amount:.2f}

📝 **שלב 3 מתוך 4: מטבע החיוב**

באיזה מטבע אתה משלם?

💡 **טיפ:** רב המנויים בישראל הם בשקלים או דולרים""",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ADD_CURRENCY
            
        except (ValueError, TypeError):
            await update.message.reply_text(
                """❌ **לא הצלחתי להבין את הסכום**

💡 **איך להקליד נכון:**
• השתמש בנקודה למספרים עשרוניים (לא פסיק)
• דוגמאות נכונות: 39.90, 15, 120.5
• אל תוסיף סימני מטבע או טקסט

🔄 **נסה שוב:**"""
            )
            return ADD_AMOUNT

    async def handle_currency_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        currency_code = query.data.split('_')[1]
        
        if currency_code == "other":
            await query.edit_message_text(
                """💱 **מטבע אחר**

הקלד את קוד המטבע (לדוגמה: GBP, JPY, CAD)
או את הסימון המלא (לדוגמה: £, ¥)

💡 **דוגמאות נפוצות:**
• GBP - פאונד בריטי
• JPY - יין יפני  
• CAD - דולר קנדי
• CHF - פרנק שוויצרי"""
            )
            return ADD_CURRENCY

        # סמלי מטבע
        currency_symbols = {
            'ILS': '₪',
            'USD': '$',
            'EUR': '€'
        }
        
        context.user_data['currency'] = currency_code
        symbol = currency_symbols.get(currency_code, currency_code)
        
        await query.edit_message_text(
            f"""💱 **מטבע נשמר:** {symbol} {currency_code}

📝 **שלב 4 מתוך 4: יום החיוב**

באיזה יום בחודש אתה מקבל את החיוב? (מספר בין 1-28)

💡 **איך למצוא:**
• בדוק בהודעות SMS של הבנק
• חפש בהיסטוריית החיובים
• בחר יום משוער אם לא בטוח

🔄 **דוגמאות:** 1, 15, 25, 28""",
            parse_mode='Markdown'
        )
        return ADD_DATE

    async def add_currency_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        currency = update.message.text.strip().upper()
        context.user_data['currency'] = currency
        
        await update.message.reply_text(
            f"""💱 **מטבע נשמר:** {currency}

📝 **שלב 4 מתוך 4: יום החיוב**

באיזה יום בחודש אתה מקבל את החיוב? (מספר בין 1-28)

💡 **איך למצוא:**
• בדוק בהודעות SMS של הבנק
• חפש בהיסטוריית החיובים
• בחר יום משוער אם לא בטוח

🔄 **דוגמאות:** 1, 15, 25, 28""",
            parse_mode='Markdown'
        )
        return ADD_DATE

    async def add_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            day = int(update.message.text.strip())
            if not 1 <= day <= 28:
                await update.message.reply_text(
                    """❌ **יום לא חוקי**

📅 **יום החיוב חייב להיות בין 1 ל-28**

💡 **למה עד 28?**
• כדי להבטיח שהיום קיים בכל חודש
• פברואר הכי קצר יש בו 28 ימים
• אם החיוב ב-31, בחר 28

🔄 **נסה שוב:**"""
                )
                return ADD_DATE

            # שמירת הנתונים
            user_id = update.effective_user.id
            ud = context.user_data
            
            self.db.add_subscription(
                user_id, ud['service_name'], ud['amount'], 
                ud['currency'], day, ud['detected_category']
            )
            self.db.log_user_action(user_id, "add_subscription_finish")

            # הודעת הצלחה מעוצבת
            emoji = self.get_category_emoji(ud['detected_category'])
            next_payment = self.get_next_payment_date(day)
            
            success_text = f"""🎉 **המנוי נוסף בהצלחה!**

{emoji} **פרטי המנוי:**
• 📋 **שירות:** {ud['service_name']}
• 💰 **סכום:** {ud['amount']:.2f} {ud['currency']}
• 📅 **יום חיוב:** {day} בחודש
• 🏷️ **קטגוריה:** {ud['detected_category'].title()}
• 📅 **תשלום הבא:** {next_payment}

💡 **מה עכשיו?**
• המנוי נשמר במערכת
• תקבל תזכורות לפני החיוב
• אפשר לצפות בסטטיסטיקות"""

            keyboard = [
                [InlineKeyboardButton("📋 צפה בכל המנויים", callback_data="my_subs")],
                [InlineKeyboardButton("➕ הוסף מנוי נוסף", callback_data="add_new_sub")],
                [InlineKeyboardButton("📊 צפה בסטטיסטיקות", callback_data="stats")]
            ]
            
            await update.message.reply_text(
                success_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            ud.clear()
            return ConversationHandler.END
            
        except (ValueError, TypeError):
            await update.message.reply_text(
                """❌ **לא הצלחתי להבין את היום**

📅 **הקלד רק מספר בין 1 ל-28**

💡 **דוגמאות נכונות:**
• 1 - לראשון בחודש
• 15 - לאמצע החודש  
• 25 - לסוף החודש
• 28 - לאחרון בחודש (בטוח)

🔄 **נסה שוב:**"""
            )
            return ADD_DATE

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        
        cancel_text = """❌ **הפעולה בוטלה**

🔄 **חזרה לתפריט הראשי**

💡 **אפשר להתחיל שוב בכל עת:**
• לחץ על "➕ הוסף מנוי חדש"
• או השתמש בכפתורי התפריט למטה"""
        
        await update.message.reply_text(
            cancel_text,
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
        return ConversationHandler.END

    # --- Edit/Delete Handlers ---
    async def delete_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        sub_id = int(context.matches[0].group(1))
        
        sub = self.db.get_subscription_by_id(sub_id, user_id)
        if not sub:
            await update.message.reply_text("❌ המנוי לא נמצא או כבר נמחק.")
            return

        emoji = self.get_category_emoji(sub['category'])
        
        text = f"""🗑️ **מחיקת מנוי**

{emoji} **האם למחוק את המנוי:**
• **שירות:** {sub['service_name']}
• **סכום:** {sub['amount']:.2f} {sub['currency']}
• **יום חיוב:** {sub['billing_day']} בחודש

⚠️ **שים לב:** פעולה זו בלתי הפיכה!"""
        
        keyboard = [[
            InlineKeyboardButton("✅ כן, מחק", callback_data=f"confirm_delete_{sub_id}"),
            InlineKeyboardButton("❌ לא, בטל", callback_data="cancel_delete")
        ]]
        
        await update.message.reply_text(
            text, 
            parse_mode='Markdown', 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
                await query.edit_message_text(
                    f"🗑️ **המנוי נמחק בהצלחה**\n\n"
                    f"❌ **{sub['service_name']}** הוסר מהמערכת"
                )
                self.db.log_user_action(user_id, f"delete_subscription_confirm_{sub_id}")
            else:
                await query.edit_message_text("❌ המנוי כבר נמחק.")
        
        elif data == "cancel_delete":
            await query.edit_message_text("✅ המחיקה בוטלה. המנוי נשמר.")
        
        elif data == "add_new_sub":
            await self.add_subscription_start(update, context)
        
        elif data == "my_subs":
            await self.my_subscriptions_command_callback(update, context)
        
        elif data == "stats":
            await self.stats_command_callback(update, context)
        
        elif data == "upcoming":
            await self.upcoming_payments_command_callback(update, context)
        
        elif data == "settings":
            await self.settings_command_callback(update, context)
        
        elif data == "help":
            await self.help_command_callback(update, context)
        
        elif data == "main_menu":
            await self.show_main_menu(update, context)
        
        elif data.startswith("settings_"):
            await self.handle_settings_callback(update, context, data)
        
        elif data == "export_data":
            await self.export_data_callback(update, context)

    async def my_subscriptions_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # העתקת הלוגיקה מ-my_subscriptions_command אבל עם callback query
        query = update.callback_query
        user_id = query.effective_user.id
        
        # שימוש בלוגיקה קיימת
        original_update = Update(
            update_id=update.update_id,
            message=query.message,
            effective_user=update.effective_user,
            effective_chat=update.effective_chat
        )
        
        await self.my_subscriptions_command(original_update, context)

    async def stats_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        original_update = Update(
            update_id=update.update_id,
            message=query.message,
            effective_user=update.effective_user,
            effective_chat=update.effective_chat
        )
        await self.stats_command(original_update, context)

    async def upcoming_payments_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        original_update = Update(
            update_id=update.update_id,
            message=query.message,
            effective_user=update.effective_user,
            effective_chat=update.effective_chat
        )
        await self.upcoming_payments_command(original_update, context)

    async def settings_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        original_update = Update(
            update_id=update.update_id,
            message=query.message,
            effective_user=update.effective_user,
            effective_chat=update.effective_chat
        )
        await self.settings_command(original_update, context)

    async def help_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        original_update = Update(
            update_id=update.update_id,
            message=query.message,
            effective_user=update.effective_user,
            effective_chat=update.effective_chat
        )
        await self.help_command(original_update, context)

    async def export_data_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        original_update = Update(
            update_id=update.update_id,
            message=query.message,
            effective_user=update.effective_user,
            effective_chat=update.effective_chat
        )
        await self.export_data_command(original_update, context)

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        
        menu_text = """🏠 **תפריט ראשי**

🎯 **בחר פעולה:**
• ➕ הוסף מנוי חדש
• 📋 צפה במנויים הפעילים
• 📊 ראה סטטיסטיקות מפורטות  
• 🗓️ בדוק תשלומים קרובים
• ⚙️ הגדרות מתקדמות
• ❓ עזרה ותמיכה

💡 **טיפ:** השתמש בכפתורי התפריט למטה לגישה מהירה!"""
        
        await query.edit_message_text(
            menu_text,
            parse_mode='Markdown',
            reply_markup=self.get_inline_main_menu()
        )

    async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
        query = update.callback_query
        
        if data == "settings_notifications":
            await query.edit_message_text(
                """🔔 **הגדרות תזכורות**

🎯 **מתי לקבל התראות:**
• 📅 3 ימים לפני חיוב
• 📅 יום לפני חיוב  
• 📅 ביום החיוב
• 🎯 הגדרה מותאמת

💡 **בקרוב:** פיצ'ר זה יפותח בעדכון הבא!""",
                parse_mode='Markdown'
            )
        
        elif data == "settings_currency":
            keyboard = [
                [InlineKeyboardButton("₪ שקל כברירת מחדל", callback_data="default_currency_ILS")],
                [InlineKeyboardButton("$ דולר כברירת מחדל", callback_data="default_currency_USD")],
                [InlineKeyboardButton("€ יורו כברירת מחדל", callback_data="default_currency_EUR")]
            ]
            await query.edit_message_text(
                """💰 **מטבע ברירת מחדל**

🎯 **בחר מטבע עיקרי:**
המטבע יוצע אוטומטי בעת הוספת מנויים חדשים

💡 **בקרוב:** פיצ'ר זה יפותח בעדכון הבא!""",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "settings_budget":
            await query.edit_message_text(
                """📊 **תקציב חודשי**

🎯 **הגדר מגבלת הוצאות:**
• קבל התראות על חריגה
• עקוב אחר השגת יעדים
• נתח את ההוצאות שלך

💡 **בקרוב:** פיצ'ר זה יפותח בעדכון הבא!""",
                parse_mode='Markdown'
            )

    async def handle_unknown_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        suggestions_text = """❓ **לא הבנתי מה אתה מחפש**

💡 **השתמש בכפתורי התפריט למטה:**
• ➕ הוסף מנוי חדש
• 📋 המנויים שלי  
• 📊 סטטיסטיקות
• 🗓️ תשלומים קרובים
• ⚙️ הגדרות
• ❓ עזרה

🔄 **או נסה פקודות:**
• /help - עזרה מלאה
• /start - התחלה מחדש"""
        
        keyboard = [[InlineKeyboardButton("❓ עזרה מלאה", callback_data="help")]]
        await update.message.reply_text(
            suggestions_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
            'streaming': ['netflix', 'disney', 'amazon prime', 'hbo', 'hulu', 'apple tv', 'yes+', 'sting', 'cellcom tv', 'hot', 'viaplay'],
            'music': ['spotify', 'apple music', 'youtube music', 'deezer', 'tidal', 'pandora'],
            'productivity': ['office', 'microsoft 365', 'notion', 'slack', 'zoom', 'asana', 'trello', 'monday', 'clickup'],
            'cloud': ['dropbox', 'google drive', 'icloud', 'one drive', 'google one', 'mega'],
            'software': ['adobe', 'photoshop', 'figma', 'canva', 'github', 'autocad', 'sketch'],
            'gaming': ['xbox', 'playstation', 'steam', 'nintendo', 'epic games', 'origin'],
            'fitness': ['gym', 'strava', 'myfitnesspal', 'nike training', 'peloton'],
            'news': ['ynet', 'haaretz', 'maariv', 'calcalist', 'new york times', 'wall street journal'],
            'communication': ['whatsapp', 'telegram', 'discord', 'teams', 'webex'],
            'financial': ['bank', 'credit', 'paypal', 'revolut', 'wise']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in service_lower for keyword in keywords):
                return category
        return 'other'

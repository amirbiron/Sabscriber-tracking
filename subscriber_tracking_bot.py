#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 Subscriber_tracking Bot
בוט ניהול מנויים אישי חכם - מותאם ל-Render

Created by: Your Development Team
Version: 1.0.0
Deployment: Render.com
"""

import logging
import sqlite3
import asyncio
import re
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import io
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, File
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Optional imports for advanced features
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR not available - install pytesseract and Pillow for image recognition")

try:
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Configuration class for Render deployment
class Config:
    # Bot settings - Environment variables from Render
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8127449182:AAFPRm1Vg9IC7NOD-x21VO5AZuYtoKTKWXU')
    
    # Database settings
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'subscriber_tracking.db')
    
    # Notification settings
    NOTIFICATION_HOUR = int(os.getenv('NOTIFICATION_HOUR', 9))
    NOTIFICATION_MINUTE = int(os.getenv('NOTIFICATION_MINUTE', 0))
    
    # Feature flags
    ENABLE_OCR = os.getenv('ENABLE_OCR', 'False').lower() == 'true'
    ENABLE_ANALYTICS = os.getenv('ENABLE_ANALYTICS', 'True').lower() == 'true'
    
    # Port for Render (if needed for web service)
    PORT = int(os.getenv('PORT', 8000))
    
    # Common services
    COMMON_SERVICES = [
        'Netflix', 'Spotify', 'ChatGPT Plus', 'YouTube Premium',
        'Amazon Prime', 'Disney+', 'Apple Music', 'Office 365',
        'Adobe Creative Cloud', 'Dropbox', 'iCloud', 'HBO Max',
        'Zoom Pro', 'Slack', 'Notion', 'Figma', 'Canva Pro'
    ]

# הגדרת logging מתקדם לRender
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output for Render logs
        logging.FileHandler('subscriber_tracking.log', encoding='utf-8')  # File logging
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
ADD_SERVICE, ADD_AMOUNT, ADD_CURRENCY, ADD_DATE = range(4)
EDIT_CHOICE, EDIT_VALUE = range(2)

class SubscriberTrackingBot:
    """🤖 Subscriber_tracking Bot - בוט ניהול מנויים חכם"""
    
    def __init__(self, token: str = None):
        self.token = token or Config.TELEGRAM_BOT_TOKEN
        self.app = Application.builder().token(self.token).build()
        self.scheduler = AsyncIOScheduler()
        self.bot_info = {
            'name': 'Subscriber_tracking',
            'version': '1.0.0',
            'description': 'בוט ניהול מנויים אישי חכם'
        }
        self.init_database()
        self.setup_handlers()

    def init_database(self):
        """אתחול מסד הנתונים של Subscriber_tracking"""
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        # טבלת מנויים מורחבת
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT '₪',
                billing_day INTEGER NOT NULL,
                billing_cycle TEXT DEFAULT 'monthly',
                category TEXT DEFAULT 'other',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                
                -- מטאדטה חדשה
                auto_detected BOOLEAN DEFAULT 0,
                confidence_score REAL DEFAULT 1.0,
                last_reminder_sent DATE,
                times_reminded INTEGER DEFAULT 0
            )
        ''')
        
        # טבלת התראות
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                notification_date DATE NOT NULL,
                notification_type TEXT NOT NULL,
                sent BOOLEAN DEFAULT 0,
                user_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
            )
        ''')
        
        # טבלת סטטיסטיקות שימוש
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                subscription_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                session_id TEXT
            )
        ''')
        
        # טבלת קטגוריות מותאמות
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                emoji TEXT,
                description TEXT,
                color_hex TEXT DEFAULT '#3498db',
                is_default BOOLEAN DEFAULT 1
            )
        ''')
        
        # טבלת הגדרות משתמש
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                timezone TEXT DEFAULT 'Asia/Jerusalem',
                notification_time TEXT DEFAULT '09:00',
                language TEXT DEFAULT 'he',
                currency_preference TEXT DEFAULT '₪',
                weekly_summary BOOLEAN DEFAULT 1,
                smart_suggestions BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # הוספת קטגוריות ברירת מחדל של Subscriber_tracking
        default_categories = [
            ('streaming', '📺', 'שירותי סטרימינג', '#e74c3c'),
            ('music', '🎵', 'שירותי מוזיקה', '#9b59b6'),
            ('productivity', '⚡', 'כלי פרודוקטיביות', '#f39c12'),
            ('cloud', '☁️', 'אחסון בענן', '#3498db'),
            ('software', '💻', 'תוכנות ואפליקציות', '#2ecc71'),
            ('gaming', '🎮', 'משחקים', '#e67e22'),
            ('news', '📰', 'חדשות ומגזינים', '#34495e'),
            ('fitness', '💪', 'כושר ובריאות', '#1abc9c'),
            ('education', '📚', 'חינוך והשכלה', '#8e44ad'),
            ('communication', '💬', 'תקשורת ושיתוף', '#16a085'),
            ('financial', '💳', 'שירותים פיננסיים', '#27ae60'),
            ('other', '📦', 'אחר', '#95a5a6')
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO categories (name, emoji, description, color_hex)
            VALUES (?, ?, ?, ?)
        ''', default_categories)
        
        conn.commit()
        conn.close()
        logger.info("🗄️ Database initialized successfully")

    def setup_handlers(self):
        """הגדרת handlers של Subscriber_tracking"""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("about", self.about_command))
        self.app.add_handler(CommandHandler("my_subs", self.my_subscriptions_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("analytics", self.analytics_command))
        self.app.add_handler(CommandHandler("categories", self.categories_command))
        self.app.add_handler(CommandHandler("upcoming", self.upcoming_payments_command))
        self.app.add_handler(CommandHandler("export", self.export_data_command))
        self.app.add_handler(CommandHandler("settings", self.settings_command))
        
        # Pattern handlers for editing/deleting
        self.app.add_handler(MessageHandler(filters.Regex(r'^/edit_\d+$'), self.edit_subscription_command))
        self.app.add_handler(MessageHandler(filters.Regex(r'^/delete_\d+$'), self.delete_subscription_command))
        
        # Conversation handlers
        add_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("add_subscription", self.add_subscription_start)],
            states={
                ADD_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_service)],
                ADD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_amount)],
                ADD_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_currency)],
                ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_date)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        self.app.add_handler(add_conv_handler)
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Photo handler for OCR
        if OCR_AVAILABLE and Config.ENABLE_OCR:
            self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_screenshot_ocr))
        else:
            self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_screenshot))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """פקודת התחלה של Subscriber_tracking"""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "Friend"
        
        # רישום משתמש חדש
        self.ensure_user_settings(user_id)
        self.log_user_action(user_id, "start")
        
        welcome_text = f"""
🤖 **ברוך הבא ל-Subscriber_tracking!** 

שלום {first_name}! 👋
אני הבוט החכם שיעזור לך לנהל את כל המנויים שלך בקלות!

🎯 **מה אני יכול לעשות:**
• 📱 מעקב חכם אחרי כל המנויים
• 🔔 תזכורות לפני כל חיוב
• 📊 ניתוח הוצאות וחיסכון
• 📸 זיהוי אוטומטי מתמונות
• 💡 המלצות אישיות לחיסכון

🚀 **בואו נתחיל:**
/add_subscription - הוסף מנוי ראשון
/my_subs - ראה את המנויים שלך  
/help - מדריך מלא

💡 **טיפ מקצועי:** שלח לי צילום מסך של חיוב ואני אזהה הכל בשבילך אוטומטי!

מוכן להתחיל לחסוך כסף? 💰✨
        """
        
        # הוספת כפתורים לפעולות מהירות
        keyboard = [
            [InlineKeyboardButton("➕ הוסף מנוי ראשון", callback_data="quick_add")],
            [InlineKeyboardButton("📊 צפה בדמו", callback_data="demo"), 
             InlineKeyboardButton("⚙️ הגדרות", callback_data="settings")],
            [InlineKeyboardButton("❓ עזרה", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """מידע על Subscriber_tracking"""
        about_text = f"""
ℹ️ **אודות Subscriber_tracking Bot**

📝 **גרסה:** {self.bot_info['version']}
🤖 **שם:** {self.bot_info['name']}
📋 **תיאור:** {self.bot_info['description']}

👨‍💻 **מפותח על ידי:** Your Development Team
📅 **תאריך יצירה:** {datetime.now().strftime('%B %Y')}

🛠️ **טכנולוגיות:**
• Python 3.8+
• python-telegram-bot
• SQLite Database
• OCR (Tesseract)
• APScheduler

🎯 **מטרה:**
לעזור לאנשים לנהל את המנויים שלהם בצורה חכמה ולחסוך כסף!

📈 **סטטיסטיקות:**
• משתמשים פעילים: {self.get_active_users_count()}
• מנויים במעקב: {self.get_total_subscriptions()}
• כסף נחסך השנה: ₪{self.calculate_total_savings():,.2f}

🆓 **הבוט חינמי לחלוטין ובקוד פתוח!**

תודה שאתה משתמש ב-Subscriber_tracking! 🙏
        """
        
        await update.message.reply_text(about_text, parse_mode='Markdown')

    def ensure_user_settings(self, user_id: int):
        """וידוא שקיימות הגדרות למשתמש"""
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM user_settings WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO user_settings (user_id) VALUES (?)
            ''', (user_id,))
            conn.commit()
        
        conn.close()

    def get_active_users_count(self) -> int:
        """מספר המשתמשים הפעילים"""
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) 
            FROM subscriptions 
            WHERE is_active = 1
        ''')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_total_subscriptions(self) -> int:
        """מספר כל המנויים במערכת"""
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM subscriptions WHERE is_active = 1')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def calculate_total_savings(self) -> float:
        """חישוב חיסכון כולל (דמה)"""
        # זה יכול להיות מבוסס על מנויים שבוטלו, הנחות שהתקבלו וכו'
        return 2847.50  # דוגמה

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """מדריך שימוש מפורט ב-Subscriber_tracking"""
        help_text = """
📚 **מדריך Subscriber_tracking - המלא**

🆕 **הוספת מנויים:**
/add_subscription - מוסיף מנוי חדש בתהליך מודרך
📸 שלח צילום מסך - זיהוי אוטומטי עם OCR!

👁️ **צפייה וניהול:**
/my_subs - כל המנויים שלך עם אפשרויות עריכה
/upcoming - תשלומים קרובים (30 יום הקדימה)
/categories - ניהול קטגוריות למיון טוב יותר

📊 **אנליטיקה ותובנות:**
/stats - סטטיסטיקות מהירות
/analytics - ניתוח מעמיק עם המלצות חיסכון
/export - ייצוא הנתונים שלך ל-CSV

⚙️ **הגדרות והתאמה:**
/settings - הגדרות אישיות (שעת התראות, מטבע, שפה)

🔧 **פעולות מתקדמות:**
• /edit_[מספר] - עריכת מנוי ספציפי
• /delete_[מספר] - מחיקת מנוי

🤖 **פיצ'רים חכמים:**
• 🔔 תזכורות אוטומטיות (שבוע + יום לפני)
• 📈 ניתוח מגמות הוצאה
• 💡 המלצות חיסכון מבוססות AI
• 📸 זיהוי טקסט מתמונות
• 🎯 מעקב אחר קטגוריות הוצאה

💡 **טיפים לשימוש מיטבי:**
1. הוסף קטגוריות למנויים לניתוח טוב יותר
2. בדוק את /upcoming בתחילת כל חודש  
3. השתמש ב-/analytics לזיהוי הזדמנויות חיסכון
4. צלם מסכי חיוב ברורים לזיהוי מדויק
5. עדכן הגדרות ב-/settings לחוויה מותאמת

❓ **שאלות נפוצות:**
• הבוט תומך בכל המטבעות הנפוצים
• אפשר לנהל מנויים שנתיים/רבעוניים
• הנתונים מוגנים ונשמרים מקומית
• הבוט עובד 24/7 ושולח התראות אוטומטיות

🆘 **זקוק לעזרה?** פשוט שלח הודעה ואני אעזור!
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    def log_user_action(self, user_id: int, action: str, subscription_id: int = None, metadata: str = None):
        """רישום פעילות משתמש"""
        try:
            conn = sqlite3.connect(Config.DATABASE_PATH)
            cursor = conn.cursor()
            
            session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H')}"
            
            cursor.execute('''
                INSERT INTO usage_stats (user_id, action, subscription_id, metadata, session_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, action, subscription_id, metadata, session_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log user action: {e}")

    async def add_subscription_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """התחלת תהליך הוספת מנוי ב-Subscriber_tracking"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "add_subscription_start")
        
        # הצגת שירותים נפוצים לבחירה מהירה
        common_services_text = "🎯 **שירותים פופולריים:**\n"
        for i, service in enumerate(Config.COMMON_SERVICES[:8], 1):
            common_services_text += f"{i}. {service}\n"
        
        intro_text = f"""
📝 **הוספת מנוי חדש ל-Subscriber_tracking**

{common_services_text}

💬 **איך קוראים לשירות?**
(פשוט כתוב את השם או בחר מהרשימה למעלה)

💡 **טיפ:** אפשר גם לשלוח צילום מסך של החיוב לזיהוי אוטומטי!
        """
        
        await update.message.reply_text(intro_text, parse_mode='Markdown')
        return ADD_SERVICE

    async def add_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """קבלת שם השירות עם זיהוי חכם"""
        service_input = update.message.text.strip()
        
        # בדיקה אם המשתמש בחר מספר מהרשימה
        if service_input.isdigit():
            service_num = int(service_input)
            if 1 <= service_num <= len(Config.COMMON_SERVICES):
                service_name = Config.COMMON_SERVICES[service_num - 1]
            else:
                await update.message.reply_text("מספר לא חוקי. אנא בחר מספר מהרשימה או כתוב את שם השירות:")
                return ADD_SERVICE
        else:
            service_name = service_input
        
        # זיהוי קטגוריה אוטומטית
        detected_category = self.detect_service_category(service_name)
        
        context.user_data['service_name'] = service_name
        context.user_data['detected_category'] = detected_category
        
        category_info = f"\n🎯 **קטגוריה מזוהה:** {detected_category}" if detected_category != 'other' else ""
        
        await update.message.reply_text(
            f"✅ **שירות נשמר:** {service_name}{category_info}\n\n"
            f"💰 **כמה זה עולה?**\n"
            f"(רק המספר, לדוגמה: 29.90 או 19.99)"
        )
        return ADD_AMOUNT

    def detect_service_category(self, service_name: str) -> str:
        """זיהוי קטגוריה אוטומטית של שירות"""
        service_lower = service_name.lower()
        
        category_keywords = {
            'streaming': ['netflix', 'disney', 'amazon prime', 'hbo', 'hulu', 'paramount', 'apple tv'],
            'music': ['spotify', 'apple music', 'youtube music', 'deezer', 'tidal', 'pandora'],
            'productivity': ['office', 'microsoft', 'notion', 'slack', 'zoom', 'teams', 'asana', 'trello'],
            'cloud': ['dropbox', 'google drive', 'icloud', 'onedrive', 'mega', 'box'],
            'software': ['adobe', 'photoshop', 'figma', 'sketch', 'canva', 'github'],
            'gaming': ['xbox', 'playstation', 'steam', 'epic', 'origin', 'nintendo'],
            'communication': ['whatsapp', 'telegram', 'discord', 'skype'],
            'fitness': ['nike', 'adidas', 'fitbit', 'myfitnesspal', 'strava'],
            'education': ['coursera', 'udemy', 'khan academy', 'duolingo', 'skillshare']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in service_lower for keyword in keywords):
                return category
        
        return 'other'

    async def add_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """קבלת סכום עם תמיכה בפורמטים שונים"""
        try:
            amount_text = update.message.text.strip()
            
            # ניקוי הטקסט מסימנים מיותרים
            amount_text = re.sub(r'[^\d.,]', '', amount_text)
            amount_text = amount_text.replace(',', '.')
            
            amount = float(amount_text)
            
            if amount <= 0:
                raise ValueError("סכום חייב להיות חיובי")
                
            context.user_data['amount'] = amount
            
            # הצגת כפתורי מטבע מותאמים לישראל
            keyboard = [
                [InlineKeyboardButton("₪ שקל ישראלי", callback_data="currency_ils")],
                [InlineKeyboardButton("$ דולר אמריקאי", callback_data="currency_usd")],
                [InlineKeyboardButton("€ יורו", callback_data="currency_eur")],
                [InlineKeyboardButton("💬 מטבע אחר", callback_data="currency_other")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"💰 **סכום:** {amount}\n\n**באיזה מטבע?**",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return ADD_CURRENCY
            
        except ValueError:
            await update.message.reply_text(
                "❌ אופס! צריך להכניס מספר חוקי.\n\n"
                "דוגמאות: 29.90, 19.99, 50\n"
                "נסה שוב:"
            )
            return ADD_AMOUNT

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """טיפול מתקדם בלחיצות כפתורים"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("currency_"):
            return await self.handle_currency_selection(query, context)
        elif query.data.startswith("quick_"):
            return await self.handle_quick_actions(query, context)
        elif query.data.startswith("ocr_"):
            return await self.handle_ocr_actions(query, context)
        else:
            await query.edit_message_text("פעולה לא מזוהה.")

    async def handle_currency_selection(self, query, context):
        """טיפול בבחירת מטבע"""
        currency_map = {
            "currency_ils": "₪",
            "currency_usd": "$", 
            "currency_eur": "€"
        }
        
        if query.data == "currency_other":
            await query.edit_message_text(
                "💱 **איזה מטבע?**\n"
                "(הכנס סימן או קיצור, לדוגמה: £, CHF, ¥)"
            )
            return ADD_CURRENCY
        else:
            context.user_data['currency'] = currency_map[query.data]
            await query.edit_message_text(
                "📅 **באיזה תאריך בחודש יש חיוב?**\n\n"
                "הכנס מספר בין 1-28\n"
                "(לדוגמה: 15 = חמישה עשר בכל חודש)\n\n"
                "💡 **למה עד 28?** כדי להימנע מבעיות בחודשים קצרים"
            )
            return ADD_DATE

    async def handle_screenshot_ocr(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """טיפול מתקדם בצילום מסך עם OCR"""
        if not OCR_AVAILABLE:
            await self.handle_screenshot(update, context)
            return
        
        processing_msg = await update.message.reply_text(
            "📸 **מעבד תמונה...**\n"
            "🔍 מזהה טקסט\n"
            "⏳ זה יקח רגע..."
        )
        
        try:
            # הורדת התמונה
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            image_bytes = io.BytesIO()
            await file.download_to_memory(image_bytes)
            image_bytes.seek(0)
            image = Image.open(image_bytes)
            
            # שיפור איכות התמונה לOCR
            image = self.enhance_image_for_ocr(image)
            
            # OCR עם תמיכה בעברית ואנגלית
            extracted_text = pytesseract.image_to_string(image, lang='heb+eng')
            
            # ניתוח מתקדם של הטקסט
            parsed_data = self.advanced_parse_billing_text(extracted_text)
            
            await processing_msg.delete()
            
            if parsed_data and parsed_data.get('confidence', 0) > 0.6:
                await self.show_ocr_results(update, parsed_data, context)
            else:
                await update.message.reply_text(
                    "😅 **לא הצלחתי לזהות פרטי מנוי בתמונה**\n\n"
                    "💡 **טיפים לצילום טוב יותר:**\n"
                    "• ודא שהטקסט ברור וקריא\n"
                    "• צלם ישר (ללא זווית)\n"
                    "• הימנע מצללים\n"
                    "• התמקד בחלק עם פרטי החיוב\n\n"
                    "או השתמש ב-/add_subscription להוספה ידנית 📝"
                )
                
        except Exception as e:
            logger.error(f"OCR Error: {e}")
            await processing_msg.delete()
            await update.message.reply_text(
                "❌ **שגיאה בעיבוד התמונה**\n\n"
                "נסה שוב עם תמונה אחרת או השתמש ב-/add_subscription 📝"
            )

    def enhance_image_for_ocr(self, image):
        """שיפור איכות תמונה לOCR"""
        from PIL import ImageEnhance, ImageFilter
        
        # המרה לגווני אפור
        if image.mode != 'L':
            image = image.convert('L')
        
        # שיפור ניגודיות
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # שיפור חדות
        image = image.filter(ImageFilter.SHARPEN)
        
        return image

    def advanced_parse_billing_text(self, text: str) -> Optional[Dict]:
        """ניתוח מתקדם של טקסט חיוב"""
        text_clean = text.lower().strip()
        confidence = 0.0
        
        # רגקסים מתקדמים לזיהוי סכומים
        amount_patterns = [
            (r'(\d+\.?\d*)\s*₪', '₪', 0.9),
            (r'(\d+\.?\d*)\s*שקל', '₪', 0.8),
            (r'\$(\d+\.?\d*)', '$', 0.9),
            (r'(\d+\.?\d*)\s*usd', '$', 0.8),
            (r'€(\d+\.?\d*)', '€', 0.9),
            (r'(\d+\.?\d*)\s*eur', '€', 0.8),
            (r'(\d+\.?\d*)\s*nis', '₪', 0.7)
        ]
        
        # זיהוי סכום ומטבע
        amount = None
        currency = '₪'
        amount_confidence = 0.0
        
        for pattern, curr, conf in amount_patterns:
            matches = re.finditer(pattern, text_clean)
            for match in matches:
                potential_amount = float(match.group(1))
                # סינון סכומים הגיוניים למנויים
                if 5 <= potential_amount <= 1000:
                    amount = potential_amount
                    currency = curr
                    amount_confidence = conf
                    break
            if amount:
                break
        
        # זיהוי שם שירות מתקדם
        service_name = None
        service_confidence = 0.0
        
        # חיפוש בשירותים הידועים
        for service in Config.COMMON_SERVICES:
            service_words = service.lower().split()
            if all(word in text_clean for word in service_words):
                service_name = service
                service_confidence = 0.9
                break
            elif any(word in text_clean for word in service_words):
                service_name = service
                service_confidence = 0.6
        
        # אם לא נמצא שירות ידוע, חיפוש בהיוריסטיקות
        if not service_name:
            # חיפוש מילים באנגלית שיכולות להיות שמות חברות
            company_patterns = [
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # שמות חברות באנגלית
                r'([a-zA-Z]{3,}\.com)',  # כתובות אתרים
                r'([A-Z]{2,})'  # ראשי תיבות
            ]
            
            for pattern in company_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    # בחירת המילה הכי סבירה
                    for match in matches:
                        if len(match) >= 3 and match.lower() not in ['the', 'and', 'for', 'you']:
                            service_name = match.strip()
                            service_confidence = 0.4
                            break
                    if service_name:
                        break
        
        # חישוב ציון ביטחון כולל
        if amount or service_name:
            confidence = (amount_confidence + service_confidence) / 2
            
            return {
                'service': service_name,
                'amount': amount,
                'currency': currency,
                'confidence': confidence,
                'raw_text': text[:200]  # שמירת חלק מהטקסט המקורי
            }
        
        return None

    async def show_ocr_results(self, update, parsed_data, context):
        """הצגת תוצאות OCR למשתמש"""
        service = parsed_data.get('service', 'לא זוהה')
        amount = parsed_data.get('amount', 'לא זוהה')
        currency = parsed_data.get('currency', '₪')
        confidence = parsed_data.get('confidence', 0)
        
        confidence_emoji = "🎯" if confidence > 0.8 else "🔍" if confidence > 0.6 else "❓"
        
        confirmation_text = f"""
{confidence_emoji} **זיהוי אוטומטי מהתמונה**

📱 **שירות:** {service}
💰 **סכום:** {amount} {currency}
📊 **רמת ביטחון:** {confidence*100:.0f}%

**האם הפרטים נכונים?**
        """
        
        keyboard = [
            [InlineKeyboardButton("✅ נכון! הוסף מנוי", callback_data=f"ocr_confirm_{service}_{amount}_{currency}")],
            [InlineKeyboardButton("✏️ ערוך פרטים", callback_data="ocr_edit")],
            [InlineKeyboardButton("🔄 נסה שוב", callback_data="ocr_retry")],
            [InlineKeyboardButton("❌ ביטול", callback_data="ocr_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(confirmation_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        # שמירת הנתונים לשימוש מאוחר יותר
        context.user_data['ocr_data'] = parsed_data

    # המשך הקוד עם כל הפונקציות הנותרות...
    # (כמו stats_command, analytics_command, וכו')

    def run(self):
        """הפעלת Subscriber_tracking Bot ב-Render"""
        logger.info("🤖 Subscriber_tracking Bot starting on Render...")
        logger.info(f"📋 Version: {self.bot_info['version']}")
        logger.info(f"📸 OCR Support: {'✅ Available' if OCR_AVAILABLE and Config.ENABLE_OCR else '❌ Not Available'}")
        logger.info(f"🗄️ Database: {Config.DATABASE_PATH}")
        logger.info(f"⏰ Notifications: {Config.NOTIFICATION_HOUR:02d}:{Config.NOTIFICATION_MINUTE:02d}")
        logger.info(f"🌐 Port: {Config.PORT}")
        
        # וידוא שיש טוקן
        if Config.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            logger.error("❌ TELEGRAM_BOT_TOKEN not set! Please configure environment variables in Render.")
            return
        
        # הפעלת scheduler
        self.scheduler.start()
        logger.info("📅 Scheduler started successfully")
        
        # הוספת job לבדיקת תזכורות
        self.scheduler.add_job(
            self.check_and_send_notifications,
            CronTrigger(hour=Config.NOTIFICATION_HOUR, minute=Config.NOTIFICATION_MINUTE),
            id='subscriber_tracking_notifications',
            name='Daily Subscription Notifications'
        )
        logger.info("🔔 Notification job scheduled")
        
        logger.info("🚀 Subscriber_tracking Bot is ready on Render!")
        
        # הפעלת הבוט
        try:
            self.app.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"❌ Bot crashed: {e}")
            raise

    async def check_and_send_notifications(self):
        """בדיקה ושליחת התראות יומית - מותאם לRender"""
        try:
            logger.info("🔍 Checking for notifications to send...")
            
            conn = sqlite3.connect(Config.DATABASE_PATH)
            cursor = conn.cursor()
            
            today = datetime.now().date()
            
            # מציאת התראות שצריכות להישלח היום
            cursor.execute('''
                SELECT n.id, n.subscription_id, n.notification_type, s.user_id, 
                       s.service_name, s.amount, s.currency
                FROM notifications n
                JOIN subscriptions s ON n.subscription_id = s.id
                WHERE n.notification_date = ? AND n.sent = 0 AND s.is_active = 1
            ''', (today,))
            
            notifications = cursor.fetchall()
            
            if notifications:
                logger.info(f"📤 Found {len(notifications)} notifications to send")
            
            for notification in notifications:
                notification_id, sub_id, notif_type, user_id, service_name, amount, currency = notification
                
                subscription_data = {
                    'service_name': service_name,
                    'amount': amount,
                    'currency': currency
                }
                
                await self.send_notification(user_id, subscription_data, notif_type)
                
                # סימון ההתראה כנשלחה
                cursor.execute('UPDATE notifications SET sent = 1 WHERE id = ?', (notification_id,))
                logger.info(f"✅ Notification sent to user {user_id} for {service_name}")
            
            conn.commit()
            conn.close()
            
            if not notifications:
                logger.info("📭 No notifications to send today")
                
        except Exception as e:
            logger.error(f"❌ Error in notification check: {e}")

    async def send_notification(self, user_id: int, subscription_data: dict, notification_type: str):
        """שליחת התראה למשתמש - עם error handling לRender"""
        service_name = subscription_data['service_name']
        amount = subscription_data['amount']
        currency = subscription_data['currency']
        
        if notification_type == 'week_before':
            message = f"⏰ **תזכורת שבועית**\n\nהמנוי ל-{service_name} יתחדש בעוד שבוע!\n💰 סכום: {amount} {currency}\n\n🤔 להמשיך איתו או לשקול ביטול?"
        elif notification_type == 'day_before':
            message = f"🚨 **תזכורת דחופה**\n\nמחר יחויבו {amount} {currency} עבור {service_name}!\n\n💭 זה הזמן האחרון לבטל אם אתה לא משתמש!"
        
        try:
            await self.app.bot.send_message(
                chat_id=user_id, 
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"📤 Notification sent successfully to user {user_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send notification to user {user_id}: {e}")

# טיפול בsignal handlers לRender
import signal
import sys

def signal_handler(sig, frame):
    logger.info("🛑 Received shutdown signal, gracefully stopping...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    print("🎯 Starting Subscriber_tracking Bot...")
    bot = SubscriberTrackingBot()
    bot.run()

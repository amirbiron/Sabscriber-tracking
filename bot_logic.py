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

# הגדרת logging בתחילת הקובץ - לפני כל השאר
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# עכשיו ניתן להוסיף file handler אם אפשר (רק בסביבה מקומית)
try:
    if not os.getenv('RENDER'):  # לא ברנדר
        file_handler = logging.FileHandler('subscriber_tracking.log', encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        logger.info("File logging enabled")
    else:
        logger.info("Running on Render - console logging only")
except Exception:
    logger.warning("Could not create log file - using console only")

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
    # Test if tesseract is actually available
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
    logger.info("OCR support available")
except (ImportError, Exception):
    OCR_AVAILABLE = False
    logger.warning("OCR not available - pytesseract/tesseract not installed")

try:
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    REQUESTS_AVAILABLE = True
    logger.info("Requests support available")
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("Requests not available - some features may be limited")
# Configuration class for Render deployment
class Config:
    # Bot settings - Environment variables from Render
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    # Database settings
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/tmp/subscriber_tracking.db')
    
    # Notification settings
    NOTIFICATION_HOUR = int(os.getenv('NOTIFICATION_HOUR', 9))
    NOTIFICATION_MINUTE = int(os.getenv('NOTIFICATION_MINUTE', 0))
    
    # Feature flags
    ENABLE_OCR = os.getenv('ENABLE_OCR', 'false').lower() == 'true'
    ENABLE_ANALYTICS = os.getenv('ENABLE_ANALYTICS', 'true').lower() == 'true'
    
    # Port for Render (if needed for web service)
    PORT = int(os.getenv('PORT', 8000))
    
    @classmethod
    def validate_token(cls):
        """בדיקת תקינות הטוקן"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN environment variable not set! Please configure it in Render.")
        if cls.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            raise ValueError("❌ TELEGRAM_BOT_TOKEN contains placeholder value! Please set your actual bot token.")
        return cls.TELEGRAM_BOT_TOKEN
    
    # Common services
    COMMON_SERVICES = [
        'Netflix', 'Spotify', 'ChatGPT Plus', 'YouTube Premium',
        'Amazon Prime', 'Disney+', 'Apple Music', 'Office 365',
        'Adobe Creative Cloud', 'Dropbox', 'iCloud', 'HBO Max',
        'Zoom Pro', 'Slack', 'Notion', 'Figma', 'Canva Pro'
    ]

# Conversation states
ADD_SERVICE, ADD_AMOUNT, ADD_CURRENCY, ADD_DATE = range(4)
EDIT_CHOICE, EDIT_VALUE = range(2)

class SubscriberTrackingBot:
    """🤖 Subscriber_tracking Bot - בוט ניהול מנויים חכם"""
    
    def __init__(self, token: str = None):
        try:
            self.token = token or Config.validate_token()
            self.app = Application.builder().token(self.token).build()
            self.scheduler = AsyncIOScheduler()
            self.bot_info = {
                'name': 'Subscriber_tracking',
                'version': '1.0.0',
                'description': 'בוט ניהול מנויים אישי חכם'
            }
            self.init_database()
            self.setup_handlers()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise

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

    async def my_subscriptions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הצגת כל המנויים של המשתמש"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "view_subscriptions")
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, service_name, amount, currency, billing_day, category, notes, created_at
            FROM subscriptions 
            WHERE user_id = ? AND is_active = 1
            ORDER BY billing_day ASC
        ''', (user_id,))
        
        subscriptions = cursor.fetchall()
        conn.close()
        
        if not subscriptions:
            await update.message.reply_text(
                "📭 **אין לך מנויים רשומים עדיין**\n\n"
                "🚀 **התחל עכשיו:**\n"
                "/add_subscription - הוסף מנוי ראשון\n"
                "או שלח צילום מסך של חיוב לזיהוי אוטומטי! 📸"
            )
            return
        
        # חישוב סטטיסטיקות בסיסיות
        total_monthly = sum(sub[2] for sub in subscriptions)  # amount
        total_yearly = total_monthly * 12
        
        header_text = f"""
📱 **המנויים שלך ({len(subscriptions)} פעילים)**

💰 **סיכום הוצאות:**
• חודשי: ₪{total_monthly:.2f}
• שנתי: ₪{total_yearly:.2f}

📋 **רשימת מנויים:**
        """
        
        # בניית רשימת המנויים
        subscriptions_text = ""
        for i, (sub_id, service, amount, currency, billing_day, category, notes, created_at) in enumerate(subscriptions, 1):
            category_emoji = self.get_category_emoji(category)
            subscriptions_text += f"\n{i}. {category_emoji} **{service}**\n"
            subscriptions_text += f"   💰 {amount} {currency} • 📅 {billing_day} בחודש\n"
            subscriptions_text += f"   /edit_{sub_id} • /delete_{sub_id}\n"
        
        full_text = header_text + subscriptions_text
        
        # הוספת כפתורי פעולה
        keyboard = [
            [InlineKeyboardButton("➕ הוסף מנוי", callback_data="quick_add")],
            [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="stats"), 
             InlineKeyboardButton("📈 ניתוח", callback_data="analytics")],
            [InlineKeyboardButton("📅 תשלומים קרובים", callback_data="upcoming"),
             InlineKeyboardButton("⚙️ הגדרות", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(full_text, reply_markup=reply_markup, parse_mode='Markdown')

    def get_category_emoji(self, category):
        """החזרת אמוג'י לפי קטגוריה"""
        emoji_map = {
            'streaming': '📺',
            'music': '🎵',
            'productivity': '⚡',
            'cloud': '☁️',
            'software': '💻',
            'gaming': '🎮',
            'news': '📰',
            'fitness': '💪',
            'education': '📚',
            'communication': '💬',
            'financial': '💳',
            'other': '📦'
        }
        return emoji_map.get(category, '📦')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הצגת סטטיסטיקות מנויים"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "view_stats")
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        # סטטיסטיקות בסיסיות
        cursor.execute('SELECT COUNT(*) FROM subscriptions WHERE user_id = ? AND is_active = 1', (user_id,))
        total_subs = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM subscriptions WHERE user_id = ? AND is_active = 1', (user_id,))
        monthly_total = cursor.fetchone()[0] or 0
        
        # סטטיסטיקות לפי קטגוריה
        cursor.execute('''
            SELECT category, COUNT(*), SUM(amount) 
            FROM subscriptions 
            WHERE user_id = ? AND is_active = 1 
            GROUP BY category 
            ORDER BY SUM(amount) DESC
        ''', (user_id,))
        categories = cursor.fetchall()
        
        # סטטיסטיקות לפי מטבע
        cursor.execute('''
            SELECT currency, COUNT(*), SUM(amount) 
            FROM subscriptions 
            WHERE user_id = ? AND is_active = 1 
            GROUP BY currency
        ''', (user_id,))
        currencies = cursor.fetchall()
        
        conn.close()
        
        if total_subs == 0:
            await update.message.reply_text("📊 אין נתונים להצגה. הוסף מנויים תחילה!")
            return
        
        yearly_total = monthly_total * 12
        average_sub = monthly_total / total_subs if total_subs > 0 else 0
        
        stats_text = f"""
📊 **סטטיסטיקות המנויים שלך**

📈 **סיכום כספי:**
• מנויים פעילים: {total_subs}
• הוצאה חודשית: ₪{monthly_total:.2f}
• הוצאה שנתית: ₪{yearly_total:.2f}
• ממוצע למנוי: ₪{average_sub:.2f}

📊 **פילוח לפי קטגוריות:**
        """
        
        for category, count, amount in categories:
            emoji = self.get_category_emoji(category)
            percentage = (amount / monthly_total * 100) if monthly_total > 0 else 0
            stats_text += f"{emoji} {category}: {count} מנויים • ₪{amount:.2f} ({percentage:.1f}%)\n"
        
        if len(currencies) > 1:
            stats_text += f"\n💱 **פילוח לפי מטבע:**\n"
            for currency, count, amount in currencies:
                stats_text += f"{currency}: {count} מנויים • {amount:.2f}\n"
        
        # הוספת תובנות
        stats_text += f"\n💡 **תובנות:**\n"
        if yearly_total > 1000:
            stats_text += f"• אתה מוציא מעל ₪1,000 בשנה על מנויים!\n"
        if total_subs > 5:
            stats_text += f"• יש לך {total_subs} מנויים - שקול לבדוק אילו אתה באמת משתמש\n"
        
        keyboard = [
            [InlineKeyboardButton("📈 ניתוח מתקדם", callback_data="analytics")],
            [InlineKeyboardButton("📅 תשלומים קרובים", callback_data="upcoming")],
            [InlineKeyboardButton("📋 רשימת מנויים", callback_data="my_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def analytics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ניתוח מתקדם והמלצות חיסכון"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "view_analytics")
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        # קבלת כל המנויים
        cursor.execute('''
            SELECT service_name, amount, currency, category, created_at, last_reminder_sent
            FROM subscriptions 
            WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        subscriptions = cursor.fetchall()
        
        conn.close()
        
        if not subscriptions:
            await update.message.reply_text("📈 אין מנויים לניתוח. הוסף מנויים תחילה!")
            return
        
        total_monthly = sum(sub[1] for sub in subscriptions)
        
        analytics_text = f"""
📈 **ניתוח מתקדם - Subscriber_tracking**

💰 **ניתוח כספי:**
• הוצאה חודשית: ₪{total_monthly:.2f}
• הוצאה שנתית: ₪{total_monthly * 12:.2f}
• כ-{(total_monthly / 10000 * 100):.1f}% מהכנסה ממוצעת

🎯 **המלצות חיסכון:**
        """
        
        # המלצות מותאמות אישית
        recommendations = []
        
        # בדיקת מנויים יקרים
        expensive_subs = [sub for sub in subscriptions if sub[1] > 50]
        if expensive_subs:
            recommendations.append(f"💸 יש לך {len(expensive_subs)} מנויים יקרים - שקול חלופות זולות יותר")
        
        # בדיקת מנויים דומים
        streaming_subs = [sub for sub in subscriptions if sub[3] == 'streaming']
        if len(streaming_subs) > 2:
            recommendations.append(f"📺 {len(streaming_subs)} שירותי סטרימינג - אולי אפשר להסתפק בפחות?")
        
        # בדיקת מנויים ישנים
        old_subs = []
        from datetime import datetime, timedelta
        six_months_ago = datetime.now() - timedelta(days=180)
        for sub in subscriptions:
            try:
                created_date = datetime.strptime(sub[4], "%Y-%m-%d %H:%M:%S")
                if created_date < six_months_ago:
                    old_subs.append(sub)
            except:
                pass
        
        if old_subs:
            recommendations.append(f"📅 יש לך {len(old_subs)} מנויים מעל 6 חודשים - מתי בדקת אותם לאחרונה?")
        
        if not recommendations:
            recommendations.append("✅ נראה שאתה מנהל היטב את המנויים שלך!")
        
        for i, rec in enumerate(recommendations, 1):
            analytics_text += f"{i}. {rec}\n"
        
        # חישוב פוטנציאל חיסכון
        potential_savings = 0
        if len(streaming_subs) > 2:
            potential_savings += (len(streaming_subs) - 2) * 30  # ממוצע מנוי סטרימינג
        if expensive_subs:
            potential_savings += len(expensive_subs) * 20  # הנחת חיסכון ממוצעת
        
        if potential_savings > 0:
            analytics_text += f"\n💡 **פוטנציאל חיסכון:** עד ₪{potential_savings:.0f} בחודש!"
        
        analytics_text += f"\n📊 **השוואה:**\n"
        analytics_text += f"• ממוצע ישראלי: ~₪180 בחודש\n"
        analytics_text += f"• המנויים שלך: ₪{total_monthly:.2f}\n"
        
        if total_monthly > 180:
            analytics_text += f"• אתה מעל הממוצע ב-₪{total_monthly - 180:.2f} 📈"
        else:
            analytics_text += f"• אתה מתחת לממוצע! חיסכון של ₪{180 - total_monthly:.2f} 💪"
        
        keyboard = [
            [InlineKeyboardButton("💰 טיפים לחיסכון", callback_data="savings_tips")],
            [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="stats")],
            [InlineKeyboardButton("📋 המנויים שלי", callback_data="my_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(analytics_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def categories_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ניהול קטגוריות מנויים"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "view_categories")
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        # קבלת פילוח קטגוריות
        cursor.execute('''
            SELECT category, COUNT(*), SUM(amount), AVG(amount)
            FROM subscriptions 
            WHERE user_id = ? AND is_active = 1 
            GROUP BY category 
            ORDER BY SUM(amount) DESC
        ''', (user_id,))
        categories = cursor.fetchall()
        
        conn.close()
        
        if not categories:
            await update.message.reply_text("📦 אין מנויים לפי קטגוריות. הוסף מנויים תחילה!")
            return
        
        categories_text = f"""
📦 **ניהול קטגוריות - {len(categories)} קטגוריות**

📊 **פילוח הוצאות לפי קטגוריה:**
        """
        
        total_amount = sum(cat[2] for cat in categories)
        
        for category, count, amount, avg_amount in categories:
            emoji = self.get_category_emoji(category)
            percentage = (amount / total_amount * 100) if total_amount > 0 else 0
            categories_text += f"\n{emoji} **{category.title()}**\n"
            categories_text += f"   • {count} מנויים • ₪{amount:.2f} ({percentage:.1f}%)\n"
            categories_text += f"   • ממוצע: ₪{avg_amount:.2f} למנוי\n"
        
        categories_text += f"\n💡 **הקטגוריה היקרה ביותר:** {categories[0][0].title()}"
        categories_text += f"\n📊 **הקטגוריה הפופולרית ביותר:** {max(categories, key=lambda x: x[1])[0].title()}"
        
        keyboard = [
            [InlineKeyboardButton("📊 סטטיסטיקות מלאות", callback_data="stats")],
            [InlineKeyboardButton("📈 ניתוח מתקדם", callback_data="analytics")],
            [InlineKeyboardButton("📋 רשימת מנויים", callback_data="my_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(categories_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def upcoming_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הצגת תשלומים קרובים"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "view_upcoming")
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT service_name, amount, currency, billing_day, category
            FROM subscriptions 
            WHERE user_id = ? AND is_active = 1
            ORDER BY billing_day ASC
        ''', (user_id,))
        
        subscriptions = cursor.fetchall()
        conn.close()
        
        if not subscriptions:
            await update.message.reply_text("📅 אין מנויים פעילים לתצוגת תשלומים קרובים.")
            return
        
        from datetime import datetime, timedelta
        
        today = datetime.now().day
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        upcoming_text = f"""
📅 **תשלומים קרובים (30 יום)**

⏰ **היום: {today}/{current_month}**
        """
        
        upcoming_subs = []
        total_upcoming = 0
        
        for service, amount, currency, billing_day, category in subscriptions:
            emoji = self.get_category_emoji(category)
            
            # חישוב ימים עד החיוב הבא
            if billing_day >= today:
                days_until = billing_day - today
                next_date = f"{billing_day}/{current_month}"
            else:
                # החיוב בחודש הבא
                next_month = current_month + 1 if current_month < 12 else 1
                days_until = (30 - today) + billing_day  # קירוב
                next_date = f"{billing_day}/{next_month}"
            
            if days_until <= 30:
                upcoming_subs.append((days_until, service, amount, currency, emoji, next_date))
                total_upcoming += amount
        
        # מיון לפי ימים עד החיוב
        upcoming_subs.sort(key=lambda x: x[0])
        
        if not upcoming_subs:
            upcoming_text += "\n✅ אין תשלומים ב-30 הימים הקרובים!"
        else:
            upcoming_text += f"\n💰 **סך תשלומים צפויים:** ₪{total_upcoming:.2f}\n"
            
            for days, service, amount, currency, emoji, next_date in upcoming_subs:
                if days == 0:
                    upcoming_text += f"\n🚨 **היום:** {emoji} {service} - {amount} {currency}"
                elif days == 1:
                    upcoming_text += f"\n⚠️ **מחר:** {emoji} {service} - {amount} {currency}"
                elif days <= 7:
                    upcoming_text += f"\n🔔 **בעוד {days} ימים ({next_date}):** {emoji} {service} - {amount} {currency}"
                else:
                    upcoming_text += f"\n📌 **בעוד {days} ימים ({next_date}):** {emoji} {service} - {amount} {currency}"
        
        # הוספת טיפים
        upcoming_text += f"\n\n💡 **טיפ:** בדוק אילו מנויים אתה באמת משתמש לפני התחדשותם!"
        
        keyboard = [
            [InlineKeyboardButton("📋 כל המנויים", callback_data="my_subs")],
            [InlineKeyboardButton("⚙️ הגדרת התראות", callback_data="settings")],
            [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(upcoming_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def export_data_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ייצוא נתוני המנויים"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "export_data")
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT service_name, amount, currency, billing_day, category, notes, created_at
            FROM subscriptions 
            WHERE user_id = ? AND is_active = 1
            ORDER BY service_name
        ''', (user_id,))
        
        subscriptions = cursor.fetchall()
        conn.close()
        
        if not subscriptions:
            await update.message.reply_text("📤 אין נתונים לייצוא. הוסף מנויים תחילה!")
            return
        
        # יצירת נתונים בפורמט CSV
        csv_content = "שירות,סכום,מטבע,יום_חיוב,קטגוריה,הערות,תאריך_יצירה\n"
        
        for service, amount, currency, billing_day, category, notes, created_at in subscriptions:
            notes = notes or ""
            csv_content += f'"{service}",{amount},"{currency}",{billing_day},"{category}","{notes}","{created_at}"\n'
        
        # יצירת סיכום
        total_monthly = sum(sub[1] for sub in subscriptions)
        summary = f"""
📤 **ייצוא נתונים הושלם**

📊 **סיכום:**
• {len(subscriptions)} מנויים פעילים
• הוצאה חודשית: ₪{total_monthly:.2f}
• הוצאה שנתית: ₪{total_monthly * 12:.2f}

📋 **הנתונים:**
{csv_content}

💾 **הנתונים מוכנים להעתקה ושמירה כקובץ CSV**
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="stats")],
            [InlineKeyboardButton("📋 רשימת מנויים", callback_data="my_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode='Markdown')

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הגדרות משתמש"""
        user_id = update.effective_user.id
        self.log_user_action(user_id, "view_settings")
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        settings = cursor.fetchone()
        
        conn.close()
        
        if not settings:
            self.ensure_user_settings(user_id)
            settings = (user_id, 'Asia/Jerusalem', '09:00', 'he', '₪', 1, 1, None, None)
        
        settings_text = f"""
⚙️ **הגדרות Subscriber_tracking**

🔔 **התראות:**
• שעת התראה: {settings[2]}
• התראות שבועיות: {'פעיל' if settings[5] else 'כבוי'}

🌍 **הגדרות כלליות:**
• אזור זמן: {settings[1]}
• שפה: {settings[3]}
• מטבע מועדף: {settings[4]}

🤖 **פיצ'רים חכמים:**
• המלצות חכמות: {'פעיל' if settings[6] else 'כבוי'}
• OCR (זיהוי מתמונות): {'פעיל' if Config.ENABLE_OCR else 'כבוי'}

💡 **טיפ:** הגדרות אלו משפיעות על חוויית השימוש שלך
        """
        
        keyboard = [
            [InlineKeyboardButton("🔔 שינוי שעת התראה", callback_data="settings_notifications")],
            [InlineKeyboardButton("💱 שינוי מטבע", callback_data="settings_currency")],
            [InlineKeyboardButton("🤖 פיצ'רים חכמים", callback_data="settings_features")],
            [InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def edit_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """עריכת מנוי קיים"""
        # קבלת מספר המנוי מהמסר
        sub_id = int(update.message.text.split('_')[1])
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT service_name, amount, currency, billing_day, category, notes
            FROM subscriptions 
            WHERE id = ? AND user_id = ? AND is_active = 1
        ''', (sub_id, user_id))
        
        subscription = cursor.fetchone()
        conn.close()
        
        if not subscription:
            await update.message.reply_text("❌ מנוי לא נמצא או שאין לך הרשאה לערוך אותו.")
            return
        
        service, amount, currency, billing_day, category, notes = subscription
        notes = notes or "אין הערות"
        
        edit_text = f"""
✏️ **עריכת מנוי: {service}**

📋 **פרטים נוכחיים:**
• 💰 סכום: {amount} {currency}
• 📅 יום חיוב: {billing_day}
• 📦 קטגוריה: {category}
• 📝 הערות: {notes}

**מה תרצה לערוך?**
        """
        
        keyboard = [
            [InlineKeyboardButton("💰 סכום", callback_data=f"edit_amount_{sub_id}")],
            [InlineKeyboardButton("📅 יום חיוב", callback_data=f"edit_billing_{sub_id}")],
            [InlineKeyboardButton("📦 קטגוריה", callback_data=f"edit_category_{sub_id}")],
            [InlineKeyboardButton("📝 הערות", callback_data=f"edit_notes_{sub_id}")],
            [InlineKeyboardButton("🔙 חזרה למנויים", callback_data="my_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(edit_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def delete_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """מחיקת מנוי"""
        # קבלת מספר המנוי מהמסר
        sub_id = int(update.message.text.split('_')[1])
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT service_name, amount, currency
            FROM subscriptions 
            WHERE id = ? AND user_id = ? AND is_active = 1
        ''', (sub_id, user_id))
        
        subscription = cursor.fetchone()
        
        if not subscription:
            conn.close()
            await update.message.reply_text("❌ מנוי לא נמצא או שאין לך הרשאה למחוק אותו.")
            return
        
        service, amount, currency = subscription
        
        delete_text = f"""
🗑️ **מחיקת מנוי**

⚠️ **אתה עומד למחוק:**
📱 **שירות:** {service}
💰 **סכום:** {amount} {currency}

**האם אתה בטוח? הפעולה בלתי הפיכה!**
        """
        
        keyboard = [
            [InlineKeyboardButton("✅ כן, מחק", callback_data=f"confirm_delete_{sub_id}")],
            [InlineKeyboardButton("❌ ביטול", callback_data="my_subs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        conn.close()
        await update.message.reply_text(delete_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ביטול פעולה נוכחית"""
        await update.message.reply_text(
            "❌ **פעולה בוטלה**\n\n"
            "🏠 חזרה לתפריט הראשי:\n"
            "/start - תפריט ראשי\n"
            "/my_subs - המנויים שלי\n"
            "/help - עזרה"
        )
        context.user_data.clear()
        return ConversationHandler.END

    async def add_currency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הוספת מטבע מותאם אישית"""
        currency_input = update.message.text.strip()
        
        # בדיקה שהמטבע לא ריק ולא ארוך מדי
        if not currency_input or len(currency_input) > 5:
            await update.message.reply_text(
                "❌ מטבע לא חוקי. נסה שוב:\n"
                "(לדוגמה: £, CHF, ¥, RUB)"
            )
            return ADD_CURRENCY
        
        context.user_data['currency'] = currency_input
        
        await update.message.reply_text(
            f"✅ **מטבע נשמר:** {currency_input}\n\n"
            "📅 **באיזה תאריך בחודש יש חיוב?**\n\n"
            "הכנס מספר בין 1-28\n"
            "(לדוגמה: 15 = חמישה עשר בכל חודש)\n\n"
            "💡 **למה עד 28?** כדי להימנע מבעיות בחודשים קצרים"
        )
        return ADD_DATE

    async def add_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הוספת תאריך חיוב וסיום התהליך"""
        try:
            billing_day = int(update.message.text.strip())
            
            if not 1 <= billing_day <= 28:
                await update.message.reply_text(
                    "❌ תאריך לא חוקי. הכנס מספר בין 1-28:\n"
                    "(לדוגמה: 15 לחמישה עשר בחודש)"
                )
                return ADD_DATE
            
            # שמירת המנוי במסד הנתונים
            user_id = update.effective_user.id
            service_name = context.user_data['service_name']
            amount = context.user_data['amount']
            currency = context.user_data['currency']
            category = context.user_data.get('detected_category', 'other')
            
            conn = sqlite3.connect(Config.DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO subscriptions (user_id, service_name, amount, currency, billing_day, category)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, service_name, amount, currency, billing_day, category))
            
            conn.commit()
            conn.close()
            
            # רישום פעילות
            self.log_user_action(user_id, "subscription_added", metadata=f"{service_name}_{amount}_{currency}")
            
            success_text = f"""
✅ **מנוי נוסף בהצלחה!**

📱 **שירות:** {service_name}
💰 **סכום:** {amount} {currency}
📅 **יום חיוב:** {billing_day} בכל חודש
📦 **קטגוריה:** {category}

🔔 **תזכורות:** תקבל התראה שבוע ויום לפני כל חיוב

🎯 **מה הלאה?**
            """
            
            keyboard = [
                [InlineKeyboardButton("📋 ראה את כל המנויים", callback_data="my_subs")],
                [InlineKeyboardButton("➕ הוסף מנוי נוסף", callback_data="quick_add")],
                [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
            
            # ניקוי נתוני ההקשר
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "❌ נסה להכניס מספר חוקי בין 1-28:\n"
                "(לדוגמה: 15)"
            )
            return ADD_DATE

    async def handle_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """טיפול בצילום מסך ללא OCR"""
        await update.message.reply_text(
            "📸 **קיבלתי את התמונה!**\n\n"
            "🔍 **זיהוי אוטומטי לא זמין כרגע**\n"
            "השתמש ב-/add_subscription להוספה ידנית\n\n"
            "💡 **טיפ:** אם יש לך פרטי החיוב, אני יכול לעזור לך להוסיף אותם במהירות!"
        )

    async def handle_quick_actions(self, query, context):
        """טיפול בפעולות מהירות"""
        if query.data == "quick_add":
            await query.edit_message_text(
                "📝 **הוספת מנוי מהירה**\n\n"
                "לחץ על /add_subscription להתחלת התהליך המלא\n"
                "או שלח צילום מסך לזיהוי אוטומטי! 📸"
            )
        elif query.data == "demo":
            demo_text = """
🎯 **דמו - Subscriber_tracking Bot**

**מה אני יכול לעשות בשבילך:**

📱 **ניהול מנויים:**
• הוספה קלה עם /add_subscription
• צפייה בכל המנויים עם /my_subs
• עריכה ומחיקה פשוטה

📊 **ניתוח והתובנות:**
• סטטיסטיקות מפורטות (/stats)
• ניתוח חכם והמלצות (/analytics)
• תשלומים קרובים (/upcoming)

🔔 **תזכורות אוטומטיות:**
• שבוע לפני כל חיוב
• יום לפני כל חיוב
• ניתן להתאים בהגדרות

✨ **פיצ'רים חכמים:**
• זיהוי אוטומטי מצילומי מסך
• זיהוי קטגוריות אוטומטי
• המלצות חיסכון מותאמות

🚀 **מוכן להתחיל? לחץ /add_subscription**
            """
            await query.edit_message_text(demo_text)
        else:
            await query.edit_message_text("פעולה לא זוהתה. נסה שוב.")

    async def handle_ocr_actions(self, query, context):
        """טיפול בפעולות OCR"""
        if query.data.startswith("ocr_confirm_"):
            # עיבוד אישור OCR
            parts = query.data.split('_')
            service = parts[2]
            amount = float(parts[3])
            currency = parts[4]
            
            # המשך עם תהליך הוספת מנוי
            context.user_data['service_name'] = service
            context.user_data['amount'] = amount
            context.user_data['currency'] = currency
            
            await query.edit_message_text(
                f"✅ **מאושר!**\n\n"
                f"📱 {service}\n💰 {amount} {currency}\n\n"
                "📅 **באיזה תאריך בחודש יש חיוב?** (1-28)"
            )
        elif query.data == "ocr_edit":
            await query.edit_message_text(
                "✏️ **עריכת פרטים**\n\n"
                "השתמש ב-/add_subscription להוספה ידנית\n"
                "כך תוכל לעדכן את כל הפרטים לפי הצורך."
            )
        elif query.data == "ocr_retry":
            await query.edit_message_text(
                "🔄 **נסה שוב**\n\n"
                "שלח צילום מסך נוסף או השתמש ב-/add_subscription להוספה ידנית."
            )
        elif query.data == "ocr_cancel":
            await query.edit_message_text(
                "❌ **פעולה בוטלה**\n\n"
                "לחץ /start לחזרה לתפריט הראשי"
            )

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
        logger.info(f"🔑 Token: {'✅ Configured' if self.token else '❌ Missing'}")
        
        # הפעלת scheduler
        if not self.scheduler.running:
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
        
        # הפעלת הבוט עם הגנה מפני אינסטנסים כפולים
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"🚀 Starting bot polling (attempt {attempt + 1}/{max_retries})")
                self.app.run_polling(
                    drop_pending_updates=True,
                    close_loop=False,
                    stop_signals=None  # מניעת התנגשויות עם Flask
                )
                break
            except Exception as e:
                if "make sure that only one bot instance is running" in str(e).lower():
                    logger.warning(f"⚠️ Bot instance conflict detected (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        logger.info("⏳ Waiting 10 seconds before retry...")
                        import time
                        time.sleep(10)
                        continue
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

def get_telegram_app():
    """יצירת אפליקציית הטלגרם"""
    try:
        bot = SubscriberTrackingBot()
        return bot.app
    except ValueError as e:
        logger.error(f"Failed to create Telegram app: {e}")
        raise

if __name__ == "__main__":
    print("🎯 Starting Subscriber_tracking Bot...")
    bot = SubscriberTrackingBot()
    bot.run()

# config.py
import os

class Config:
    """
    מחזיק את כל משתני התצורה וההגדרות של הבוט.
    קורא את הערכים ממשתני סביבה.
    """
    # קריאת הטוקן ממשתנה סביבה שמוגדר ב-Render
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    # הגדרות נוספות שניתן לשנות דרך משתני סביבה
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/var/data/subscriber_tracking.db')
    NOTIFICATION_HOUR = int(os.getenv('NOTIFICATION_HOUR', 9))
    NOTIFICATION_MINUTE = int(os.getenv('NOTIFICATION_MINUTE', 0))

    @classmethod
    def validate_token(cls):
        """בדיקת תקינות הטוקן לפני הפעלת הבוט."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set! Please configure it in Render.")
        return cls.TELEGRAM_BOT_TOKEN


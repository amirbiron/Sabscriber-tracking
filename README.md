# 🤖 Subscriber_tracking Bot

> **בוט טלגרם חכם לניהול מנויים ושליטה בהוצאות**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-20.0-blue.svg)](https://python-telegram-bot.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![OCR Support](https://img.shields.io/badge/OCR-Tesseract-orange.svg)](https://github.com/tesseract-ocr/tesseract)

## 🎯 מה זה Subscriber_tracking?

**Subscriber_tracking** הוא בוט טלגרם מתקדם שעוזר לך לנהל את כל המנויים שלך במקום אחד, לעקוב אחרי הוצאות ולחסוך כסף באמצעות תזכורות חכמות וניתוח מתקדם.

### ✨ למה Subscriber_tracking מיוחד?

- 📸 **זיהוי אוטומטי**: שלח צילום מסך של חיוב והבוט יזהה הכל אוטומטי
- 🔔 **תזכורות חכמות**: התראות שבוע ויום לפני כל חיוב
- 📊 **אנליטיקה מתקדמת**: ניתוח הוצאות והמלצות חיסכון מבוססות נתונים
- 🎯 **קטגוריות חכמות**: מיון אוטומטי לפי סוג השירות
- 💰 **מעקב רב-מטבעי**: תמיכה בשקל, דולר, יורו ועוד
- 📱 **ממשק ידידותי**: עברית מלאה עם emoji וכפתורים

## 🚀 התחלה מהירה

### 1. צור בוט בטלגרם

```bash
# פתח את @BotFather בטלגרם ושלח:
/newbot

# שם הבוט: Subscriber Tracking Bot
# Username: subscriber_tracking_bot (או כל username זמין)
# שמור את הטוקן!
```

### 2. הכנה מקומית

```bash
# צור תיקייה לפרויקט
mkdir subscriber_tracking_bot
cd subscriber_tracking_bot

# שמור את הקבצים מהארטיפקטים למעלה:
# - subscriber_tracking_bot.py (הקוד הראשי)  
# - config.py (הגדרות)
# - .env (עותק מ-.env.example עם הטוקן שלך)

# יצור סביבה וירטואלית
python -m venv venv
source venv/bin/activate  # Linux/Mac
# או
venv\Scripts\activate     # Windows

# התקן dependencies
pip install python-telegram-bot==20.0 apscheduler==3.10.4 python-dotenv pytesseract Pillow
```

### 3. הגדרה

צור קובץ `.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_PATH=subscriber_tracking.db
NOTIFICATION_HOUR=9
NOTIFICATION_MINUTE=0
ENABLE_OCR=true
ENABLE_ANALYTICS=true
```

### 4. הפעלה

```bash
python subscriber_tracking_bot.py
```

## 📋 פיצ'רים

### 🔥 פיצ'רים בסיסיים

- ✅ **הוספת מנויים**: תהליך מודרך קל ופשוט
- ✅ **מעקב תשלומים**: רשימת המנויים עם תאריכי חיוב
- ✅ **תזכורות אוטומטיות**: התראות לפני כל חיוב
- ✅ **עריכה ומחיקה**: ניהול מלא של המנויים
- ✅ **סטטיסטיקות**: סיכום הוצאות חודשי ושנתי

### ⚡ פיצ'רים מתקדמים

- 📸 **OCR (זיהוי טקסט)**: זיהוי אוטומטי מצילומי מסך
- 📊 **אנליטיקה חכמה**: ניתוח מגמות והמלצות חיסכון
- 🎯 **קטגוריות אוטומטיות**: מיון לפי סוג השירות
- 📅 **תחזית הוצאות**: חיזוי הוצאות לחודשים הבאים
- 📁 **ייצוא נתונים**: CSV עבור ניתוח חיצוני
- ⚙️ **הגדרות אישיות**: התאמה לשעות ומטבע

### 🤖 AI ואוטומציה

- 🧠 **זיהוי שירותים חכם**: הכרה אוטומטית של שירותים פופולריים
- 💡 **המלצות חיסכון**: ניתוח דפוסי צריכה וייעוץ
- 📈 **ניתוח מגמות**: זיהוי עליות והתחזיות עתידיות
- 🔄 **אופטימיזציה אוטומטית**: הצעות לאיחוד/ביטול מנויים

## 📱 פקודות זמינות

### פקודות בסיסיות
```
/start - התחלה והכרות עם הבוט
/add_subscription - הוספת מנוי חדש
/my_subs - צפייה בכל המנויים
/help - מדריך שימוש מפורט
```

### פקודות מתקדמות
```
/stats - סטטיסטיקות מהירות
/analytics - ניתוח מעמיק עם המלצות
/upcoming - תשלומים קרובים (30 יום)
/categories - ניהול קטגוריות
/export - ייצוא נתונים לCSV
/settings - הגדרות אישיות
```

### פקודות ניהול
```
/edit_[מספר] - עריכת מנוי ספציפי
/delete_[מספר] - מחיקת מנוי
/about - מידע על הבוט
```

## 🔧 טכנולוגיות

### Backend
- **Python 3.8+** - שפת הפיתוח הראשית
- **python-telegram-bot 20.0** - ספריית הבוט
- **SQLite** - מסד נתונים מקומי
- **APScheduler** - מערכת תזכורות

### AI & OCR
- **Tesseract OCR** - זיהוי טקסט מתמונות
- **PIL/Pillow** - עיבוד תמונות
- **Regex Patterns** - ניתוח חכם של טקסט

### Analytics
- **Pandas** (אופציונלי) - ניתוח נתונים
- **Matplotlib** (אופציונלי) - גרפים וויזואליזציה

## 📁 מבנה הפרויקט

```
subscriber_tracking_bot/
├── subscriber_tracking_bot.py    # הקובץ הראשי
├── config.py                     # הגדרות
├── requirements.txt              # Dependencies
├── .env.example                  # דוגמה להגדרות
├── README.md                     # המדריך הזה
├── docs/                         # תיעוד מפורט
│   ├── installation.md           # מדריך התקנה
│   ├── usage.md                  # מדריך שימוש
│   └── api.md                    # תיעוד API
└── tests/                        # בדיקות
    ├── test_bot.py
    └── test_ocr.py
```

## 🎯 דוגמאות שימוש

### הוספת מנוי ידנית
```
/add_subscription
-> "Netflix"
-> "55"
-> ₪ (בחירה מהכפתורים)
-> "15" (תאריך חיוב)
✅ מנוי נוסף בהצלחה!
```

### זיהוי אוטומטי מתמונה
```
[שלח צילום מסך של חיוב]
🔍 מזהה טקסט...
✅ זוהה: Spotify Premium - 19.90₪
[לחץ "אישור" להוספה]
```

### קבלת תזכורות
```
⏰ שבוע לפני: "המנוי ל-Netflix יתחדש בעוד שבוע!"
🚨 יום לפני: "מחר יחויבו 55₪ עבור Netflix"
```

## 🔧 התקנה מתקדמת

### עם OCR Support
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-heb

# macOS
brew install tesseract tesseract-lang

# Windows
# הורד מ: https://github.com/UB-Mannheim/tesseract/wiki
```

### הפעלה כשירות (Linux)
```bash
# צור service file
sudo nano /etc/systemd/system/subscriber-tracking.service

# הפעל השירות
sudo systemctl enable subscriber-tracking
sudo systemctl start subscriber-tracking
```

## 📊 ניטור ולוגים

הבוט שומר לוגים מפורטים:
- פעילות משתמשים
- שגיאות OCR
- התראות שנשלחו
- ביצועי מערכת

```bash
# צפייה בלוגים
tail -f subscriber_tracking.log

# ניטור בזמן אמת
python subscriber_tracking_bot.py --verbose
```

## 🤝 תרומה לפרויקט

אנחנו מזמינים תרומות! כך תוכל לעזור:

1. **Fork** את הפרויקט
2. צור **branch** חדש (`git checkout -b feature/amazing-feature`)
3. **Commit** את השינויים (`git commit -m 'Add amazing feature'`)
4. **Push** ל-branch (`git push origin feature/amazing-feature`)
5. פתח **Pull Request**

### אזורים לתרומה
- 🌍 תרגום לשפות נוספות
- 🎨 שיפור UI/UX
- 🔧 אופטימיזציה של OCR
- 📱 תמיכה בפלטפורמות נוספות
- 🧪 הוספת בדיקות

## 🐛 דיווח על באגים

מצאת באג? עזור לנו לתקן!

1. בדוק אם הבאג כבר דווח ב-[Issues](../../issues)
2. אם לא, פתח issue חדש עם:
   - תיאור מפורט של הבעיה
   - צעדים לשחזור
   - לוגים רלוונטיים
   - מידע על הסביבה (OS, Python version)

## 📋 Roadmap

### גרסה 1.1
- [ ] תמיכה ב-WhatsApp Business API
- [ ] שילוב עם Google Calendar
- [ ] אפליקציית Web נלווית
- [ ] API ציבורי

### גרסה 1.2
- [ ] זיהוי אוטומטי מאימיילים
- [ ] שילוב עם בנקים (Open Banking)
- [ ] ניתוח AI מתקדם
- [ ] דשבורד וויזואליזציה

### גרסה 2.0
- [ ] מלחמה בהונאות
- [ ] משא ומתן אוטומטי עם ספקים
- [ ] קהילת שיתוף והמלצות
- [ ] יישום mobile נטיבי

## 📜 רישיון

הפרויקט הזה מופץ תחת רישיון MIT. ראה את קובץ `LICENSE` לפרטים מלאים.

## 🙏 תודות

- [python-telegram-bot](https://python-telegram-bot.org/) - ספריית הבוט המעולה
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - מנוע זיהוי הטקסט
- הקהילה המדהימה של מפתחי Python

## 📞 יצירת קשר

- 📧 **Email**: [contact@subscriber-tracking.com](mailto:contact@subscriber-tracking.com)
- 💬 **Telegram**: [@subscriber_tracking_support](https://t.me/subscriber_tracking_support)
- 🐛 **Issues**: [GitHub Issues](../../issues)
- 📖 **Documentation**: [Wiki](../../wiki)

---

**Made with ❤️ in Israel**

*Subscriber_tracking - כי כל שקל חשוב! 💰*

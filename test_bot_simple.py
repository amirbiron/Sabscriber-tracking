#!/usr/bin/env python3
"""
🤖 Simple Test Bot - Hebrew/English
פשוט לבדוק אם הבוט עובד
"""
import os
import asyncio
from telegram.ext import Application, CommandHandler

async def start(update, context):
    """פקודת התחלה"""
    welcome_text = """
🤖 **הבוט עובד!** 

✅ הבוט מחובר ומגיב לפקודות
🎉 Bot is working and responding to commands!

**פקודות זמינות:**
/start - התחלה
/help - עזרה  
/status - סטטוס הבוט
/test - בדיקה
"""
    await update.message.reply_text(welcome_text)

async def help_cmd(update, context):
    """פקודת עזרה"""
    help_text = """
🤖 **מדריך השימוש:**

**פקודות בסיסיות:**
/start - התחלה והודעת ברוכים הבאים
/help - מדריך זה
/status - בדיקת סטטוס הבוט
/test - בדיקת חיבור

**מידע טכני:**
- הבוט פועל על Python 3.13
- משתמש ב-python-telegram-bot
- תומך בעברית ואנגלית

**זקוק לעזרה?** פשוט כתוב הודעה!
"""
    await update.message.reply_text(help_text)

async def status(update, context):
    """סטטוס הבוט"""
    import platform
    import sys
    
    status_text = f"""
✅ **סטטוס הבוט:**

🟢 **פועל**: הבוט מחובר ותקין
🐍 **Python**: {sys.version.split()[0]}
🖥️ **מערכת**: {platform.system()}
🤖 **מגיב**: לכל הפקודות

**Last check**: זה עתה ✨
"""
    await update.message.reply_text(status_text)

async def test_command(update, context):
    """בדיקת חיבור"""
    await update.message.reply_text("🧪 **בדיקה עברה בהצלחה!** Test passed successfully! ✅")

async def handle_message(update, context):
    """טיפול בהודעות רגילות"""
    user_message = update.message.text
    response = f"""
📩 **קיבלתי את ההודעה שלך:**
"{user_message}"

🤖 **הבוט עובד ומגיב!**
להצגת פקודות זמינות: /help
"""
    await update.message.reply_text(response)

async def main():
    """הפעלת הבוט"""
    # בדיקת טוקן
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        print("📝 Please set the TELEGRAM_BOT_TOKEN environment variable")
        print("🔑 Get your token from @BotFather on Telegram")
        return
    
    print("🚀 Starting Simple Test Bot...")
    print(f"🔑 Token: {token[:10]}...")
    
    try:
        # יצירת אפליקציה
        app = Application.builder().token(token).build()
        
        # הוספת handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("test", test_command))
        
        # הודעות רגילות
        from telegram.ext import MessageHandler, filters
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("✅ Bot initialized successfully!")
        print("🔄 Starting polling...")
        print("🤖 Bot is now running and ready to respond to commands!")
        print("📱 Go to Telegram and send /start to your bot")
        
        # הפעלת הבוט
        await app.run_polling()
        
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        print("🔍 Check your token and try again")

if __name__ == '__main__':
    asyncio.run(main())
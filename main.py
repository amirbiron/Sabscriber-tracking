import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import http.server
import socketserver
import threading
from datetime import datetime, time, timedelta
import pymongo

# --- הגדרות בסיסיות ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- קבועים ומשתני סביבה ---
TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
PORT = int(os.environ.get("PORT", 8080))

# --- הגדרת מסד הנתונים ---
client = pymongo.MongoClient(MONGO_URI)
db = client.get_database("SubscriptionBotDB")
subscriptions_collection = db.get_collection("subscriptions")

# --- הגדרת שלבים לשיחה (Conversation) ---
NAME, DAY, COST, CONFIRM = range(4)

# --- שרת Keep-Alive ---
def run_keep_alive_server():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        logger.info(f"Keep-alive server started on port {PORT}")
        httpd.serve_forever()

# --- פונקציות הבוט ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "שלום! אני בוט שיעזור לך לעקוב אחר המנויים החודשיים שלך.\n"
        "אני אשלח לך תזכורת יום לפני כל חיוב.\n\n"
        "השתמש בפקודות הבאות:\n"
        "/add - להוספת מנוי חדש\n"
        "/mysubs - להצגת כל המנויים שלך\n"
        "/delete - למחיקת מנוי"
    )

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מתחיל את תהליך הוספת המנוי."""
    await update.message.reply_text("בוא נוסיף מנוי חדש. מה שם השירות? (למשל, ChatGPT)")
    return NAME

async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מקבל את שם המנוי ומבקש את יום החיוב."""
    context.user_data['name'] = update.message.text
    await update.message.reply_text("מצוין. באיזה יום בחודש מתבצע החיוב? (מספר בין 1 ל-31)")
    return DAY

async def received_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מקבל את יום החיוב ומבקש את העלות."""
    try:
        day = int(update.message.text)
        if not 1 <= day <= 31:
            raise ValueError()
        context.user_data['day'] = day
        await update.message.reply_text("מעולה. מה העלות החודשית? (רשום רק מספר, למשל 20)")
        return COST
    except ValueError:
        await update.message.reply_text("זה לא נראה כמו יום תקין בחודש. אנא שלח מספר בין 1 ל-31.")
        return DAY

async def received_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מקבל את העלות ומבקש אישור."""
    try:
        cost = float(update.message.text)
        context.user_data['cost'] = cost
        
        # הצגת סיכום לאישור
        summary = (
            f"שם: {context.user_data['name']}\n"
            f"יום חיוב: {context.user_data['day']} בחודש\n"
            f"עלות: {context.user_data['cost']}"
        )
        reply_keyboard = [['כן, הוסף', 'לא, בטל']]
        await update.message.reply_text(
            f"האם לאשר את הוספת המנוי הבא?\n\n{summary}",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
        )
        return CONFIRM
    except ValueError:
        await update.message.reply_text("זה לא נראה כמו מספר. אנא שלח רק את סכום העלות.")
        return COST

async def confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מאשר ושומר את המנוי במסד הנתונים."""
    if update.message.text == 'כן, הוסף':
        subscription_data = {
            "chat_id": update.effective_chat.id,
            "service_name": context.user_data['name'],
            "billing_day": context.user_data['day'],
            "cost": context.user_data['cost'],
        }
        subscriptions_collection.insert_one(subscription_data)
        await update.message.reply_text("המנוי נוסף בהצלחה!", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("ההוספה בוטלה.", reply_markup=ReplyKeyboardRemove())
        
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מבטל את תהליך ההוספה."""
    await update.message.reply_text("הפעולה בוטלה.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

async def my_subs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """מציג למשתמש את כל המנויים הרשומים שלו."""
    user_subs = subscriptions_collection.find({"chat_id": update.effective_chat.id})
    subs_list = list(user_subs)
    
    if not subs_list:
        await update.message.reply_text("לא רשומים לך מנויים כרגע. השתמש ב- /add כדי להוסיף.")
        return

    message = "אלו המנויים הרשומים שלך:\n\n"
    total_cost = 0
    for sub in subs_list:
        message += f"- **{sub['service_name']}**\n  חיוב ב-{sub['billing_day']} לחודש, עלות: {sub['cost']}\n"
        total_cost += sub['cost']
        
    message += f"\n**סה\"כ עלות חודשית: {total_cost}**"
    await update.message.reply_text(message, parse_mode='Markdown')

# (פונקציות למחיקה הן יותר מורכבות, נשאיר אותן לשדרוג עתידי)

# --- משימה מתוזמנת ---
async def daily_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """בודק פעם ביום אילו מנויים עומדים להתחדש מחר."""
    logger.info("Running daily subscription check...")
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_day = tomorrow.day
    
    # מצא את כל המנויים שהחיוב שלהם הוא מחר
    subs_due_tomorrow = subscriptions_collection.find({"billing_day": tomorrow_day})
    
    for sub in subs_due_tomorrow:
        message = (
            f"🔔 **תזכורת תשלום** 🔔\n\n"
            f"מחר, {tomorrow.strftime('%d/%m')}, יתבצע חיוב עבור המנוי שלך ל-**{sub['service_name']}** "
            f"בסך **{sub['cost']}**."
        )
        try:
            await context.bot.send_message(chat_id=sub['chat_id'], text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send reminder to {sub['chat_id']}: {e}")


# --- פונקציה ראשית ---
def main() -> None:
    if not TOKEN or not MONGO_URI:
        logger.fatal("FATAL: BOT_TOKEN or MONGO_URI environment variables are missing!")
        return

    keep_alive_thread = threading.Thread(target=run_keep_alive_server)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    application = Application.builder().token(TOKEN).build()
    
    # הגדרת שיחת הוספת המנוי
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_command)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_day)],
            COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_cost)],
            CONFIRM: [MessageHandler(filters.Regex('^(כן, הוסף|לא, בטל)$'), confirm_add)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mysubs", my_subs_command))
    
    # הגדרת הבדיקה היומית שתרוץ כל יום בשעה 09:00 בבוקר
    application.job_queue.run_daily(daily_check, time=time(hour=9, minute=0))
    
    logger.info("Bot starting with Polling...")
    application.run_polling()

if __name__ == "__main__":
    main()

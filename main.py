import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
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
NAME, DAY, COST = range(3)

# --- שרת Keep-Alive ---
def run_keep_alive_server():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        logger.info(f"Keep-alive server started on port {PORT}")
        httpd.serve_forever()

# --- פונקציות תפריטים ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("➕ הוספת מנוי חדש", callback_data="add_sub")],
        [InlineKeyboardButton("📋 הצגת המנויים שלי", callback_data="my_subs")],
        [InlineKeyboardButton("➖ מחיקת מנוי", callback_data="delete_sub_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- פונקציות הבוט ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # שמירת המשתמש בבסיס הנתונים אם הוא לא קיים
    user_collection = db.get_collection("users")
    user_collection.update_one({"chat_id": update.effective_chat.id}, {"$set": {"username": update.effective_user.username}}, upsert=True)
    
    await update.message.reply_text(
        "שלום! אני בוט שיעזור לך לעקוב אחר המנויים החודשיים שלך.\n"
        "אני אשלח לך תזכורת 4 ימים לפני כל חיוב.\n\n"
        "השתמש בתפריט הכפתורים כדי להתחיל:",
        reply_markup=get_main_menu()
    )

async def main_menu_callback(query, text="תפריט ראשי:"):
    """פונקציית עזר להצגת התפריט הראשי."""
    await query.edit_message_text(text, reply_markup=get_main_menu())

async def add_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מתחיל את תהליך הוספת המנוי."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("בוא נוסיף מנוי חדש. מה שם השירות? (למשל, ChatGPT)")
    return NAME

async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text("מצוין. באיזה יום בחודש מתבצע החיוב? (מספר בין 1 ל-31)")
    return DAY

async def received_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        day = int(update.message.text)
        if not 1 <= day <= 31: raise ValueError()
        context.user_data['day'] = day
        await update.message.reply_text("מעולה. מה העלות החודשית? (רשום רק מספר, למשל 20)")
        return COST
    except ValueError:
        await update.message.reply_text("זה לא נראה כמו יום תקין בחודש. אנא שלח מספר בין 1 ל-31.")
        return DAY

async def received_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        cost = float(update.message.text)
        context.user_data['cost'] = cost
        
        subscription_data = {
            "chat_id": update.effective_chat.id,
            "service_name": context.user_data['name'],
            "billing_day": context.user_data['day'],
            "cost": context.user_data['cost'],
        }
        subscriptions_collection.insert_one(subscription_data)
        await update.message.reply_text("המנוי נוסף בהצלחה!")
        
        # חזרה לתפריט הראשי
        await update.message.reply_text("תפריט ראשי:", reply_markup=get_main_menu())
        
    except ValueError:
        await update.message.reply_text("זה לא נראה כמו מספר. אנא שלח רק את סכום העלות.")
        return COST
    finally:
        context.user_data.clear()
        return ConversationHandler.END

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("הפעולה בוטלה.")
    await update.message.reply_text("תפריט ראשי:", reply_markup=get_main_menu())
    context.user_data.clear()
    return ConversationHandler.END

async def my_subs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_subs = subscriptions_collection.find({"chat_id": query.effective_chat.id})
    subs_list = list(user_subs)
    
    if not subs_list:
        await query.edit_message_text("לא רשומים לך מנויים כרגע.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")]]))
        return

    message = "אלו המנויים הרשומים שלך:\n\n"
    total_cost = 0
    for sub in subs_list:
        message += f"- **{sub['service_name']}** (חיוב ב-{sub['billing_day']} לחודש, עלות: {sub['cost']})\n"
        total_cost += sub['cost']
        
    message += f"\n**סה\"כ עלות חודשית: {total_cost}**"
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")]]))

async def delete_sub_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_subs = list(subscriptions_collection.find({"chat_id": query.effective_chat.id}))
    if not user_subs:
        await query.edit_message_text("אין לך מנויים למחוק.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")]]))
        return
        
    keyboard = []
    for sub in user_subs:
        button = InlineKeyboardButton(f"❌ {sub['service_name']}", callback_data=f"delete_{sub['_id']}")
        keyboard.append([button])
    keyboard.append([InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")])
    
    await query.edit_message_text("בחר מנוי למחיקה:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_sub_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    sub_id_str = query.data.split('_')[1]
    from bson.objectid import ObjectId
    
    subscriptions_collection.delete_one({"_id": ObjectId(sub_id_str)})
    await query.answer("המנוי נמחק!")
    await main_menu_callback(query, text="המנוי נמחק. תפריט ראשי:")

# --- משימה מתוזמנת ---
async def daily_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running daily subscription check...")
    # **השינוי כאן: בודקים 4 ימים קדימה**
    reminder_date = datetime.now() + timedelta(days=4)
    reminder_day = reminder_date.day
    
    subs_due = subscriptions_collection.find({"billing_day": reminder_day})
    
    for sub in subs_due:
        message = (
            f"🔔 **תזכורת תשלום** 🔔\n\n"
            f"בעוד 4 ימים, בתאריך {reminder_date.strftime('%d/%m')}, יתבצע חיוב עבור המנוי שלך ל-**{sub['service_name']}** "
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
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_sub_callback, pattern="^add_sub$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_day)],
            COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_cost)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        conversation_timeout=60
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(my_subs_callback, pattern="^my_subs$"))
    application.add_handler(CallbackQueryHandler(delete_sub_menu_callback, pattern="^delete_sub_menu$"))
    application.add_handler(CallbackQueryHandler(delete_sub_confirm_callback, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: main_menu_callback(u.callback_query), pattern="^main_menu$"))

    application.job_queue.run_daily(daily_check, time=time(hour=9, minute=0))
    
    logger.info("Bot starting with Polling...")
    application.run_polling()

if __name__ == "__main__":
    main()

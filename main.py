import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- התיקון לקונפליקט של asyncio ---
import nest_asyncio
nest_asyncio.apply()
# ------------------------------------

# ודא שהייבוא תואם לשמות הקבצים שלך
from config import Config
from bot_logic import SubscriberTrackingBot

# הגדרת לוגינג בסיסי
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- שרת דמה (Keep-Alive) עבור Render ---
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """עונה לבקשות GET עם הודעת "חי"."""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot service is alive.")

def run_dummy_server(port: int):
    """מריץ את שרת הדמה בכתובת והפורט הנתונים."""
    server_address = ('', port)
    try:
        httpd = HTTPServer(server_address, KeepAliveHandler)
        logger.info(f"🌐 Dummy server running on port {port}")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"💥 Dummy server failed: {e}")

# --- פונקציית הפעלת הבוט ---
def start_bot():
    """מאמת את הטוקן ומפעיל את הבוט."""
    logger.info("🚀 Starting Subscriber_tracking Bot...")
    try:
        # 1. קבל את הטוקן ממחלקת התצורה
        token = Config.validate_token()

        # 2. צור את אובייקט הבוט והעבר לו את הטוקן
        bot = SubscriberTrackingBot(token=token)
        
        # 3. הפעל את לולאת הריצה של הבוט
        bot.run()

    except ValueError as e:
        logger.critical(f"🚨 Configuration error: {e}")
    except Exception as e:
        logger.critical(f"❌ A critical error occurred while starting the bot: {e}")

# --- נקודת כניסה ראשית ---
if __name__ == "__main__":
    # קבל את הפורט ממשתני הסביבה של Render, עם ברירת מחדל
    port = int(os.environ.get('PORT', 10000))

    # הרץ את שרת הדמה בתהליכון (thread) נפרד כדי לא לחסום את הבוט
    server_thread = threading.Thread(target=run_dummy_server, args=(port,))
    server_thread.daemon = True  # מאפשר לתוכנית להיסגר גם אם התהליכון רץ
    server_thread.start()

    # הפעל את הבוט בתהליכון הראשי
    start_bot()

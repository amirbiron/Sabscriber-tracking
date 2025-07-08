#!/usr/bin/env python3
"""
🚀 Subscriber_tracking Bot - Render Entry Point
"""

import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from subscriber_tracking_bot import SubscriberTrackingBot
from subscriber_tracking_bot import Config  # חשוב!

# הגדרת logging ל-Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# שרת HTTP מדומה כדי ש-Render יזהה פורט פתוח
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write("✅ Subscriber_tracking Bot is running".encode("utf-8"))

def run_dummy_server():
    port = Config.PORT
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    logger.info(f"🌐 Dummy HTTP server running on port {port}")
    server.serve_forever()

def main():
    logger.info("🚀 Starting Subscriber_tracking Bot on Render...")

    try:
        # הפעלת שרת הדמה בת'רד נפרד
        threading.Thread(target=run_dummy_server, daemon=True).start()

        bot = SubscriberTrackingBot()
        logger.info("✅ Bot initialized successfully")
        bot.run()
    except ValueError as ve:
        if "TELEGRAM_BOT_TOKEN" in str(ve):
            logger.error("❌ Token validation failed!")
            logger.error("📋 To fix this issue:")
            logger.error("   1. Go to https://t.me/BotFather on Telegram")
            logger.error("   2. Create a new bot or use /token to get existing token")
            logger.error("   3. Set TELEGRAM_BOT_TOKEN in Render environment variables")
            logger.error("   4. Redeploy your service")
        else:
            logger.error(f"❌ Validation error: {ve}")
        return
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()

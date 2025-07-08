#!/usr/bin/env python3
"""
🚀 Entry point for Subscriber_tracking Bot - Web + Bot for Render
"""

import os
import logging
import requests
import threading
from flask import Flask
from bot_logic import SubscriberTrackingBot

# לוגים
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# יצירת Flask app לRender
app = Flask(__name__)

@app.route('/')
def health_check():
    """Endpoint בסיסי לRender"""
    return {
        "status": "active",
        "service": "Subscriber_tracking Bot",
        "message": "🤖 Bot is running successfully!"
    }

@app.route('/health')
def health():
    """Health check endpoint"""
    return {"status": "healthy", "bot": "running"}

def run_bot():
    """הרצת הבוט בthread נפרד"""
    try:
        logger.info("🚀 Starting Subscriber_tracking Bot...")
        
        # First check if token is available
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
            logger.error("📝 Please set the TELEGRAM_BOT_TOKEN environment variable in Render:")
            logger.error("   1. Go to your Render dashboard")
            logger.error("   2. Select your service")
            logger.error("   3. Go to Environment tab")
            logger.error("   4. Add: TELEGRAM_BOT_TOKEN = your_bot_token_here")
            logger.error("   5. Redeploy the service")
            return

        try:
            requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
            logger.info("🔧 Webhook deleted.")
        except Exception as e:
            logger.warning(f"⚠️ Couldn't delete webhook: {e}")

        # הפעלת הבוט
        bot = SubscriberTrackingBot()
        logger.info("📡 Bot started successfully!")
        bot.run()
        
    except ValueError as e:
        logger.error(f"❌ Bot initialization failed: {e}")
        logger.error("📝 Please check your TELEGRAM_BOT_TOKEN configuration in Render")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise

def main():
    """הפעלת Flask + Bot"""
    logger.info("🌟 Starting Subscriber_tracking Bot service for Render...")
    
    # הפעלת הבוט בthread נפרד
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("🤖 Bot thread started")
    
    # הפעלת Flask server
    port = int(os.getenv('PORT', 8000))
    logger.info(f"🌐 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()

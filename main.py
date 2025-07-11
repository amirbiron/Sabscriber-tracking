#!/usr/bin/env python3 """ 🚀 Entry point for Subscriber_tracking Bot - Worker Service """

import os import logging import requests import asyncio from bot_logic import SubscriberTrackingBot import threading from http.server import BaseHTTPRequestHandler, HTTPServer

לוגים

logging.basicConfig( level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s' ) logger = logging.getLogger(name)

שרת dummy כדי לשמור על הפורט פתוח

class DummyHandler(BaseHTTPRequestHandler): def do_GET(self): self.send_response(200) self.end_headers() self.wfile.write(b"✔️ Bot is alive")

def run_dummy_server(): port = int(os.environ.get("PORT", 10000)) server = HTTPServer(("0.0.0.0", port), DummyHandler) logger.info(f"🌐 Dummy server running on port {port}") server.serve_forever()

async def start_bot(): logger.info("🚀 Starting Subscriber_tracking Bot...")

token = os.getenv('TELEGRAM_BOT_TOKEN')
if not token:
    logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
    return

try:
    response = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
    logger.info(f"🔧 Webhook deleted: {response.json()}")
except Exception as e:
    logger.warning(f"⚠️ Couldn't delete webhook: {e}")

try:
    bot = SubscriberTrackingBot()
    logger.info("📱 Bot initialized")
    await bot.run()
except Exception as e:
    logger.exception(f"❌ Unexpected error inside bot: {e}")

הפעלת השרת הדמי כ-thread

threading.Thread(target=run_dummy_server, daemon=True).start()

מפעילים את ה״event loop של Render – בלי asyncio.run()

loop = asyncio.get_event_loop() loop.create_task(start_bot()) loop.run_forever()


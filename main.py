import asyncio
import logging
from bot_logic import SubscriberTrackingBot

# הגדרת לוגים בסיסית (אם אין לך כבר)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = SubscriberTrackingBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "already running" in str(e):
            logger.warning("Event loop already running, using existing loop")
            loop = asyncio.get_event_loop()
            loop.create_task(main())
            loop.run_forever()
        else:
            raise

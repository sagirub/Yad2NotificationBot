"""
Development mode: Run the bot using long polling.
This is for local development only. In production, use the webhook handler.

Usage:
    python -m src.bot.run_polling
"""
import asyncio
import logging
import sys

# Load environment variables before importing bot
from dotenv import load_dotenv
load_dotenv()

from src.bot.bot_instance import dp, bot
from src.bot.router import bot_router


async def main():
    """Main function to start polling."""
    # Attach all your handlers to the dispatcher
    dp.include_router(bot_router)

    logging.info("🤖 Bot started (polling mode)... Press CTRL+C to stop")
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def run():
    """Entry point for the polling bot."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())


if __name__ == "__main__":
    run()
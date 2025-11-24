import asyncio
import logging
import sys
from bot.bot_instance import dp, bot
from bot.router import bot_router

async def main():
    """Main function to start polling."""
    # Attach all your handlers to the dispatcher
    dp.include_router(bot_router)

    print("Bot started (polling)... Press CTRL+C to stop")
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
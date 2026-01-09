import logging

from fastapi import APIRouter, Request
from aiogram import Bot, Dispatcher, Router, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from src.config import settings

# Import handlers directly to register them on fresh routers
from src.bot.handlers import start, add_search, list_searches

router = APIRouter()

# Global dispatcher - reused across warm Lambda invocations
_dp = None


def get_dispatcher():
    """Get or create dispatcher instance."""
    global _dp
    
    # Create dispatcher if not exists
    if _dp is None:
        storage = MemoryStorage()
        _dp = Dispatcher(storage=storage)
        
        # Create a fresh main router and include all handlers
        main_router = Router()
        main_router.include_router(start.router)
        main_router.include_router(add_search.router)
        main_router.include_router(list_searches.router)
        
        _dp.include_router(main_router)
    
    return _dp


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    This is the single endpoint that Telegram sends updates to.
    """
    bot = None
    
    try:
        # Get the update from the request
        update_data = await request.json()
        
        # Create a fresh bot for each request (aiogram handles session internally)
        bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        
        # Get the dispatcher
        dp = get_dispatcher()
        
        # Validate and convert it to an aiogram Update object
        update = types.Update.model_validate(update_data, context={"bot": bot})
        
        # Feed it to the dispatcher to be processed by your handlers
        await dp.feed_update(bot, update)
        
        return {"ok": True}
        
    except Exception as e:
        logging.error(f"Error processing update: {e}", exc_info=True)
        # Still return 200 OK to Telegram to prevent it
        # from resending the same failed update.
        return {"ok": True, "error": str(e)}
    
    finally:
        # Always close the bot session to prevent resource leaks
        if bot:
            try:
                await bot.session.close()
            except Exception:
                pass  # Ignore errors during cleanup
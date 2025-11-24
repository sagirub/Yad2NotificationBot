import logging
from fastapi import APIRouter, Request, HTTPException
from aiogram import types
from bot.bot_instance import dp, bot  # Import the shared singletons
from bot.router import bot_router      # Import your main handlers

router = APIRouter()

# Attach all your handlers to the dispatcher *once* when this module is loaded.
# This is crucial for Lambda performance.
dp.include_router(bot_router)

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    This is the single endpoint that Telegram sends updates to.
    """
    try:
        # Get the update from the request
        update_data = await request.json()
        
        # Validate and convert it to an aiogram Update object
        update = types.Update.model_validate(update_data, context={"bot": bot})
        
        # Feed it to the dispatcher to be processed by your handlers
        await dp.feed_update(update)
        
        return {"ok": True}
        
    except Exception as e:
        logging.error(f"Error processing update: {e}", exc_info=True)
        # Still return 200 OK to Telegram to prevent it
        # from resending the same failed update.
        return {"ok": True, "error": str(e)}
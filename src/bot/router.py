from aiogram import Router
from bot.handlers import start, add_search, list_searches

# This is your main router
bot_router = Router()

# Include all your modular handler routers
bot_router.include_router(start.router)
bot_router.include_router(add_search.router)
bot_router.include_router(list_searches.router)
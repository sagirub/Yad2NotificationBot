# src/bot/bot_instance.py

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from config import settings

# Use MemoryStorage for FSM.
# For Lambda, this will only persist per-request, which is fine
# for a short conversation (like adding a search).
storage = MemoryStorage()

bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML") 
)

# Create Bot and Dispatcher instances as singletons
dp = Dispatcher(storage=storage)

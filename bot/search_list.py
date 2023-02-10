# encoding: utf-8

import logging

# Telegram API framework core imports
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes

# Bot constants
from bot.constants import *

from connectors.db import Search

# Init logger
logger = logging.getLogger(__name__)


async def search_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /searchlist is issued."""

    # get all user's searches from the db
    user_searches_query = [search for search in Search.scan(Search.chat_id == update.effective_chat.id)]

    message = SEARCH_LIST_TEXT
    if not user_searches_query:
        message = EMPTY_SEARCH_LIST_TEXT
    else:
        for user_search in user_searches_query:
            message += (
                f'{user_search.name}\n'
                'לחץ למחיקת החיפוש: '
                f'/ds\_{str(user_search.id)}'
                '\n'
            )

    buttons = [
        [
            InlineKeyboardButton(MENU_BUTTON_TEXT, callback_data=str(MENU))
        ]
    ]

    keyboard = InlineKeyboardMarkup(buttons)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

    return DELETE_SEARCH

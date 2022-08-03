# encoding: utf-8

import logging

# Telegram API framework core imports
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CallbackContext

# Bot constatns
from constants import *

from db import Search

#Init logger
logger = logging.getLogger(__name__)


async def search_list(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """Send a message when the command /searchlist is issued."""
    
    # TODO: get list of searches by the user, contains - search id with search name,
    # link to the search and link to command to delete the search
    # USE SEARCH_LIST_TEXT

    # get all user's searches from the db
    user_searches_query = Search.select().where(Search.chat_id == update.effective_chat.id)
    
    message = SEARCH_LIST_TEXT
    if not user_searches_query.exists():
        message = EMPTY_SEARCH_LIST_TEXT
    else:
        for user_search in user_searches_query:
            message += (
                f'{user_search.search_name}\n'
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

    #await update.callback_query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode='Markdown',
        reply_markup = keyboard
    )

    return DELETE_SEARCH
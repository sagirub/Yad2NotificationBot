# encoding: utf-8

import logging
from datetime import datetime

# Telegram API framework core imports
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes

# Bot constants
from constants import *

# DB search model
from models import Search

# Yad2 utils
from yad2wrapper import validate_search_url

# Init logger
logger = logging.getLogger(__name__)


async def add_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /search is issued or the user type the add search button in menu."""

    await update.effective_message.reply_text(ADD_SEARCH_MESSAGE)

    return ADD_SEARCH_LINK


async def add_search_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get the search link from the user after the command /search is issued"""
    search_url = update.message.text

    # send temporary message about url validation
    await_message_while_validating_search_url = \
        await update.message.reply_text(VALIDATING_SEARCH_LINK_AWAIT_MESSAGE)

    # validate the search link the user entered
    logger.info(f'Validating the search url - {search_url} for the user {update.message.from_user.id}')
    if not validate_search_url(search_url, access_check=True):
        logger.error(f'Failed to validate the search url - {search_url} of user {update.message.from_user.id}')
        await update.message.reply_text(text=ADD_SEARCH_LINK_ERROR_MESSAGE)
        # retry
        return ADD_SEARCH_LINK

    # delete the temporary message about url validation
    await await_message_while_validating_search_url.delete()

    context.user_data['search_link'] = search_url

    await update.message.reply_text(text=ADD_SEARCH_LINK_MESSAGE)

    return ADD_SEARCH_NAME


async def add_search_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get the name of the search after getting the search link"""
    search_name = update.message.text
    search_link = context.user_data['search_link']

    message = ADD_SEARCH_SUCCESS_END_MESSAGE

    # add the new search to the db
    try:
        new_search = Search(
            url=search_link,
            chat_id=update.message.from_user.id,
            name=search_name,
            last_scan_time=str(datetime.now().isoformat()))
        new_search.save()

        logger.info(f'new search was successfully added: user_id:{update.message.from_user.id}, \
                    user_name: {update.message.chat.first_name}, \
                    search_name: {search_name}, search_link: {search_link}')
    except Exception as e:
        message = ADD_SEARCH_FAIL_END_MESSAGE
        logger.error(f'failed to add a new search. user_id:{update.message.from_user.id}, \
                            user_name: {update.message.chat.first_name}, \
                            search_name: {search_name}, search_link: {search_link}')
        logger.error(e, exc_info=True)

    # delete user search link from context
    del context.user_data['search_link']

    buttons = [
        [
            InlineKeyboardButton(MENU_BUTTON_TEXT, callback_data=str(MENU))
        ]
    ]

    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(text=message, reply_markup=keyboard)

    return END

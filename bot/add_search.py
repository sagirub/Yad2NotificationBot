# encoding: utf-8

import logging
from urllib import parse

# Telegram API framework core imports
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CallbackContext

# Bot constants
from bot.constants import *

from connectors.db import Search

# Init logger
logger = logging.getLogger(__name__)


async def add_search(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """Send a message when the command /search is issued or the user type the add search button in menu."""

    await update.callback_query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=ADD_SEARCH_MESSAGE
    )

    return ADD_SEARCH_LINK


async def add_search_link(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """Get the search link from the user after the command /search is issued"""
    search_link = update.message.text

    # validate its valid yad2 search url
    parsed_url = parse.urlparse(search_link)

    # TODO: MAYBE NEED A DEEP CHECK HERE? BROWSE THE LINK AND VALIDATE THAT IS A REAL SEARCH?
    if parsed_url.netloc != YAD2_VALID_NETLOC:
        await update.message.reply_text(text=ADD_SEARCH_LINK_ERROR_MESSAGE)

        return ADD_SEARCH_LINK

    context.user_data['search_link'] = f'{parsed_url.path}?{parsed_url.query}'
    
    await update.message.reply_text(text=ADD_SEARCH_LINK_MESSAGE)

    return ADD_SEARCH_NAME


async def add_search_name(update: Update, context: CallbackContext.DEFAULT_TYPE) -> int:
    """Get the name of the search after getting the search link"""
    search_name = update.message.text
    search_link = context.user_data['search_link']

    message = ADD_SEARCH_SUCCESS_END_MESSAGE

    # add the new search to the db
    try:
        new_search = Search(
            url=search_link,
            chat_id=update.message.from_user.id,
            name=search_name)
        new_search.save()

        logger.info(f'new search was successfully added: user_id:{update.message.from_user.id}, \
                    user_name: {update.message.chat.first_name}, \
                    search_name: {search_name}, search_link: {search_link}')
    except Exception as error:
        message = ADD_SEARCH_FAIL_END_MESSAGE
        logger.error(f'failed to add a new search. user_id:{update.message.from_user.id}, \
                            user_name: {update.message.forward_sender_name}, \
                            search_name: {search_name}, search_link: {search_link}')
        logger.error(error)

    # delete user search link from context
    del context.user_data['search_link']

    buttons = [
        [
            InlineKeyboardButton(MENU_BUTTON_TEXT, callback_data=str(MENU))
        ]
    ]

    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(text=message, reply_markup=keyboard)

    return MENU

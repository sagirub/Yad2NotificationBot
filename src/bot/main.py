# coding: utf-8

import logging
import asyncio
import json

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters
)
from telegram import Update

from start_menu import start, cancel, menu
from add_search import add_search, add_search_link, add_search_name, add_search_commercial_ads
from search_list import search_list
from delete_search import delete_search
from error_handler import error_handler
from constants import *


# initialize logger
logger = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.INFO)
logging.info(f'starting bot in {"debug" if DEBUG else "prod"} mode')


async def set_my_bot_commands(application: Application) -> None:
    """Callback function to set bot commands after bot initialization"""
    await application.bot.set_my_commands([
        ('start', 'Start the bot'),
        ('add_search', 'Add new search to track'),
        ('list', 'Your tracking list')
    ])


application = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .post_init(set_my_bot_commands)
    .build()
)


def load_conversation_handlers(application: Application) -> None:
    """Load all conversation handlers"""

    logging.info('loading conversation handlers')

    # stateless commands
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('list', search_list))
    application.add_handler(CallbackQueryHandler(search_list, pattern=f'^{str(SEARCH_LIST)}$'))
    application.add_handler(CallbackQueryHandler(menu, pattern=f'^{str(MENU)}$'))
    application.add_handler(MessageHandler(filters.Regex(DELETE_SEARCH_REGEX_PATTERN), delete_search))

    # add new search conversation handler
    add_search_conversation = ConversationHandler(
        entry_points=[CommandHandler('add_search', add_search),
                      CallbackQueryHandler(add_search, pattern=f'^{str(ADD_SEARCH)}$')],
        states={
            ADD_SEARCH_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_search_link)],
            ADD_SEARCH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_search_name)],
            ADD_SEARCH_COMMERCIAL_ADS: [CallbackQueryHandler(add_search_commercial_ads, pattern='^answer_')]
        },
        fallbacks=[MessageHandler(filters.COMMAND, cancel)],
        allow_reentry=True
    )

    application.add_handler(add_search_conversation)
    application.add_error_handler(error_handler)


def debug_main() -> None:
    """ debug main - run the bot using polling """

    try:
        load_conversation_handlers(application)
        logger.info('start polling...')
        application.run_polling(drop_pending_updates=True)
    except Exception as error:
        logger.error(error)


async def main(event, context) -> None:
    """prod main - Run the bot using webhook with lambda"""

    load_conversation_handlers(application)

    try:
        await application.initialize()
        await application.process_update(
            Update.de_json(json.loads(event["body"]), application.bot)
        )

        return {
            'statusCode': 200,
            'body': 'Success'
        }

    except Exception as error:
        logger.error(error)

        return {
            'statusCode': 500,
            'body': 'Failure'
        }


def lambda_handler(event, context):
    return asyncio.get_event_loop().run_until_complete(main(event, context))


if __name__ == "__main__":
    if DEBUG:
        debug_main()

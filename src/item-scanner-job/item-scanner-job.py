import os
import logging
import requests
from datetime import datetime

from models import Search

from yad2wrapper import get_search_item_ids
from yad2utils import *

# initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BOT_TOKEN = os.environ['BOT_TOKEN']


def send_telegram_bot_message(bot_token: str, chat_id: int, message: str) -> None:
    """ send a regular message from a bot to user by his chat id """

    params = {
        "chat_id": chat_id,
        "text": message
    }
    requests.get(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        params=params
    )


def send_telegram_bot_message_with_link(bot_token: str, chat_id: int, link: str, link_text: str) -> None:
    """ send a markdown message (can contain link as text) from a bot to user by his chat id """

    params = {
        "chat_id": chat_id,
        "text": f'[{link_text}]({link})',
        "parse_mode": "markdown",
    }
    requests.get(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        params=params
    )


def scan_new_items() -> None:
    """
    Start the scanning job.
    iterate over all searches in the db, scan for new items that added after the last scan time,
    notify the new items to the user.
    """

    logger.info('starting scan items job')

    for search in Search.scan():

        # convert last scan time to israel time zone because last scan time in my lambda is in utc timezone
        search_last_scan_time = datetime.fromisoformat(search.last_scan_time)

        # get the updated search item ids from yad2
        # filter only items that the user have not seen yet - that posted after the last scan time
        # if there was a failure while getting the new ads, continue to the next search
        try:
            logger.info(f'request new ads of search id: {search.id}, name: {search.name}, '
                        f'for only the ads posted after: {search.last_scan_time}')
            new_item_ids = get_search_item_ids(search_parameters=search.url, min_addition_date=search_last_scan_time)
        except Exception as exception:
            logger.error(f"failed to get search: {search.id}, {search.name} new ads", exception)
            continue

        # if there are new items - notify them to the user
        if new_item_ids:
            logger.info(f'{len(new_item_ids)} new ads seen for search id: {search.id},name: {search.name}')

            send_telegram_bot_message(BOT_TOKEN, search.chat_id, f'נצפו מודעות חדשות בחיפוש: {search.name}')

            for item_id in new_item_ids:
                send_telegram_bot_message_with_link(BOT_TOKEN,
                                                    search.chat_id, f'{ITEM_API_BASE_URL}{item_id}',
                                                    'לחץ כאן לפתיחת למודעה')

        #  update last scan time in the db
        search.update(actions=[Search.last_scan_time.set(str(datetime.now().isoformat()))])


def lambda_handler(event, context):
    try:
        scan_new_items()
    except Exception as error:
        logger.error(error)



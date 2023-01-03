import os
import logging
import requests
import pytz
from datetime import datetime

from connectors.db import Search

from yad2.yad2wrapper import get_search_item_ids
from yad2.yad2utils import *

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
    """ send a markdown message (can contains link as text) from a bot to user by his chat id """

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

    logger.info('starting scan new items job')

    for search in Search.scan():

        # convert last scan time to israel time zone because last scan time in my lambda is in utc timezone
        last_scan_time_converted_to_israel_timezone = \
            datetime.strptime(search.last_scan_time, YAD2_DATETIME_STRING_FORMAT). \
                astimezone(tz=pytz.timezone('Asia/Jerusalem')).strftime(YAD2_DATETIME_STRING_FORMAT)

        # get the updated search item ids from yad2
        # filter only items that the user have not seen - that their adding time is after minimum add time
        logger.info(f'request updated items of search id: {search.id}, name: {search.name},'
                    f' last scan time: {search.last_scan_time}')
        updated_item_ids = get_search_item_ids(search_parameters=search.url,
                                               min_addition_date=last_scan_time_converted_to_israel_timezone)

        logger.info(
            f'successfully get {len(updated_item_ids)} updated_item_ids for for search: {search.id},'
            f' {search.name}, notify them to the user')

        # if there are new item - notify them to the user
        if updated_item_ids:
            send_telegram_bot_message(BOT_TOKEN, search.chat_id, f'נצפו מודעות חדשות בחיפוש: {search.name}')

            for new_item_id in updated_item_ids:
                send_telegram_bot_message_with_link(BOT_TOKEN,
                                                    search.chat_id, f'{ITEM_API_BASE_URL}{new_item_id}',
                                                    'לחץ כאן לפתיחת למודעה')

        #  update last scan time in the db
        search.update(actions=[Search.last_scan_time.set(str(datetime.now().strftime(YAD2_DATETIME_STRING_FORMAT)))])


def lambda_handler(event, context):
    try:
        scan_new_items()
    except Exception as error:
        logger.error(error)



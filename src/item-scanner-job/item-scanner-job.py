import logging
from datetime import datetime

from models import Search

from yad2wrapper import get_search_item_ids
from yad2constants import *
from basictelegram import send_telegram_bot_message, send_telegram_bot_message_with_link

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
            new_item_ids = get_search_item_ids(search_url=search.url,
                                               commercial_items=search.commercial_ads,
                                               min_addition_date=search_last_scan_time)
        except Exception as e:
            logger.error(f'failed to get search: {search.id}, {search.name} new ads')
            logger.error(e, exc_info=True)
            continue

        # if there are new items - notify them to the user
        if new_item_ids:
            logger.info(f'{len(new_item_ids)} new ads seen for search id: {search.id},name: {search.name}')

            send_telegram_bot_message(search.chat_id, f'נצפו מודעות חדשות בחיפוש: {search.name}')

            for item_id in new_item_ids:
                send_telegram_bot_message_with_link(search.chat_id,
                                                    f'{ITEM_API_BASE_URL}{item_id}',
                                                    'לחץ כאן לפתיחת למודעה')

        #  update last scan time in the db
        search.update(actions=[Search.last_scan_time.set(str(datetime.now().isoformat()))])


def lambda_handler(event, context):
    try:
        scan_new_items()
    except Exception as error:
        logger.error(error)

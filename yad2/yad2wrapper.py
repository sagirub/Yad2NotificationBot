import requests
import logging

from yad2utils import *

# Init logger
logger = logging.getLogger(__name__)


def get_search_item_ids(search_parameters: str, only_first_page: bool = False) -> list:
    '''
    TODO
    '''

    logger.info(f'start get search items for search {search_parameters}')
    # request the jsom contains all the search items
    search_api_url = SEARCH_API_BASE_URL + search_parameters

    try:
        # TODO: combine more headers, use external library?
        response = requests.get(
            search_api_url,
            headers={'Accept': 'application/json'},
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f'the was an error while requesting the search base api\n{e}')

    # TODO: validate the response (status code, is json, not captcha, etc...) handle exceptions

    json_response = response.json()
    item_ids = [item['link_token'] for item in json_response['data']['feed']['feed_items'] if 'link_token' in item]
    total_pages = json_response['data']['feed']['total_pages'] if not only_first_page else 1

    # get the item ids of the next pages
    # if the only_first_page is False then the this for loop will not execute
    for page_id in range(2, total_pages + 1):
        # TODO: combine more headers,  use external library?
        logger.info(f'request page {page_id}')
        try:
            response = requests.get(
                f'{search_api_url}&page={page_id}',
                headers={'Accept': 'application/json'},
            )
        except requests.exceptions.RequestException as e:
            logger.error(f'the was an error while requesting the search base api\n{e}')

        # TODO: VALIDATION
        item_ids.extend(
            [item['link_token'] for item in response.json()['data']['feed']['feed_items'] if 'link_token' in item])

    logger.info(f'successfully get search items, {len(item_ids)} items retrieved')

    return item_ids

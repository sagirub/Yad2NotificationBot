import requests
import logging
import sys

from yad2.yad2utils import *

# Init logger
logger = logging.getLogger(__name__)


def get_search_item_ids(search_parameters: str, only_first_page: bool = False, max_pages: int = sys.maxsize) -> list:
    """
    Gets the current item ids appears in search by the search parameters

    Parameters
    ----------
    search_parameters : str
        The url parameters of the search to find his current item ids
    only_first_page : bool, optional
        A flag used to get only the items from the first page -
        To avoid requests if they are not needed (default is False)
    max_pages: int, optional
        A int used to limit the number of search's pages to request
        (to avoid unnecessary requests of old items)
        default value is integer max

    Returns
    -------
    list
        a list of strings contains the current item ids of search
    """

    logger.info(f'start get search items for search {search_parameters}')
    search_api_url = SEARCH_API_BASE_URL + search_parameters.strip("/")

    try:
        response = requests.get(
            search_api_url,
            headers={'Accept': 'application/json'},
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f'there was an error while requesting {search_api_url}\n{e}')
        raise e


    # TODO: validate the response (status code, is json, not captcha, etc...) handle exceptions

    json_response = response.json()
    item_ids = [item['link_token'] for item in json_response['data']['feed']['feed_items'] if 'link_token' in item]
    total_pages = json_response['data']['feed']['total_pages'] if not only_first_page else 1

    # get the item ids of the next pages
    # if the only_first_page is False then the this for loop will not execute
    for page_id in range(2, min(total_pages + 1, max_pages)):
        # TODO: combine more headers,  use external library?
        logger.info(f'request page {page_id}')
        try:
            response = requests.get(
                f'{search_api_url}&page={page_id}',
                headers={'Accept': 'application/json'},
            )
        except requests.exceptions.RequestException as e:
            logger.error(f'there was an error while requesting {f"{search_api_url}&page={page_id}"}\n{e}')

        # TODO: VALIDATION
        item_ids.extend(
            [item['link_token'] for item in response.json()['data']['feed']['feed_items'] if 'link_token' in item])

    logger.info(f'successfully get search items, {len(item_ids)} items retrieved')

    return item_ids

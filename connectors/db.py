import os
import logging

from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute
from base64 import b64encode
from hashlib import md5

logger = logging.getLogger(__name__)


class Search(Model):
    class Meta:
        table_name = "searches_prod"

        if not os.getenv('PROD', False):
            # for running local fake dynamo db (using DynamoDB Local or dynalite)
            host = "http://localhost:8000"

    id = UnicodeAttribute(hash_key=True)
    url = UnicodeAttribute()
    chat_id = NumberAttribute()
    name = UnicodeAttribute()
    last_scan_time = UnicodeAttribute()

    def save(self, **kwargs):
        """
        Generates the shortened code before saving
        """
        self.id = b64encode(
            md5(self.url.encode('utf-8')).hexdigest()[-4:].encode('utf-8')
        ).decode('utf-8').replace('=', '').replace('/', '_')
        super(Search, self).save(**kwargs)


def create_table():
    """ creates the search table in dynamodb if there aren't exists"""
    if not Search.exists():
        Search.create_table(wait=True, read_capacity_units=10, write_capacity_units=10)

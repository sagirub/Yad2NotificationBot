import os

from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, NumberAttribute, BooleanAttribute
from base64 import b64encode
from hashlib import md5


class Search(Model):
    id = UnicodeAttribute(hash_key=True)
    url = UnicodeAttribute()
    chat_id = NumberAttribute()
    name = UnicodeAttribute()
    commercial_ads = BooleanAttribute(default=False)
    last_scan_time = UnicodeAttribute()

    class Meta:
        table_name = os.environ.get("DB_TABLE_NAME", "searches")
        billing_mode = 'PAY_PER_REQUEST'
        # used when running local dynamodb host
        host = os.environ.get("DYNAMODB_HOST", None)
        region = os.environ.get("REGION")

    def save(self, **kwargs):
        """
        Generates the shortened code before saving
        """
        self.id = b64encode(
            md5(self.url.encode('utf-8')).hexdigest()[-4:].encode('utf-8')
        ).decode('utf-8').replace('=', '').replace('/', '_')
        super(Search, self).save(**kwargs)

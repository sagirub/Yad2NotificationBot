import logging

from peewee import SqliteDatabase
from peewee import Model, BigIntegerField, CharField, ForeignKeyField

logger = logging.getLogger(__name__)

# TODO: ADD TO ENV FILES
DATABASE_PATH = 'my_database.db'

db = SqliteDatabase(DATABASE_PATH)

class BaseModel(Model):
    class Meta:
        database = db


class Search(BaseModel):
    chat_id = BigIntegerField(unique=False)
    search_name = CharField()
    search_url = CharField()


class Item(BaseModel):
    item_id = CharField(primary_key=True)
    search = ForeignKeyField(Search, backref='items')

def create_tables() -> None:
    with db:
        db.create_tables([Search, Item])

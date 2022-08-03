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


class User(BaseModel):
    chat_id = BigIntegerField(primary_key=True)
    name = CharField()


class Search(BaseModel):
    User = ForeignKeyField(User, backref='searches')
    search_name = CharField()
    search_url = CharField()


class Item(BaseModel):
    item_id = CharField(primary_key=True)
    search = ForeignKeyField(Search, backref='items')


def create_tables() -> None:
    with db:
        db.create_tables([User, Search, Item])

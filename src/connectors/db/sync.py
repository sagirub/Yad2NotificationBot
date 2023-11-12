from .models import Search

""" creates the search table in dynamodb if not exists yet"""
if not Search.exists():
    Search.create_table(wait=True, read_capacity_units=1, write_capacity_units=1)

from backend.database import ObjectDatabase
from backend.database import Database


database = ObjectDatabase()

def get_db() -> Database:
    return database

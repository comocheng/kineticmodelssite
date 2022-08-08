from backend.database import Database, ObjectDatabase

database = ObjectDatabase()


def get_db() -> Database:
    return database

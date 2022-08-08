import pytest

from backend.database import ObjectDatabase


@pytest.fixture
def database() -> ObjectDatabase:
    return ObjectDatabase()

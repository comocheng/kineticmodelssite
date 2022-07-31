from typing import FrozenSet

from backend.models.utils import Model


class Author(Model):
    firstname: str
    lastname: str


class Source(Model):
    doi: str
    prime_id: str
    publication_year: int
    title: str
    journal_name: str
    journal_volume: str
    page_numbers: str
    authors: FrozenSet[Author]

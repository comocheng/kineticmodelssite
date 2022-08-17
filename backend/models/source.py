from dataclasses import field
from uuid import UUID, uuid4

from pydantic import confrozenset
from pydantic.dataclasses import dataclass

from backend.models.model import Model


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
    authors: confrozenset(Author, min_items=0)

from dataclasses import field
from uuid import UUID, uuid4

from pydantic import conlist
from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class Author:
    firstname: str
    lastname: str


@dataclass(frozen=True)
class Source:
    doi: str
    prime_id: str
    publication_year: int
    title: str
    journal_name: str
    journal_volume: str
    page_numbers: str
    authors: conlist(Author, min_items=0, unique_items=True)
    id: UUID = field(default_factory=uuid4, compare=False)

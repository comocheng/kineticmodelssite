from dataclasses import dataclass
from typing import FrozenSet


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
    authors: FrozenSet[Author]

from typing import FrozenSet

from .utils import frozen_dataclass


@frozen_dataclass
class Author:
    firstname: str
    lastname: str


@frozen_dataclass
class Source:
    doi: str
    prime_id: str
    publication_year: int
    title: str
    journal_name: str
    journal_volume: str
    page_numbers: str
    authors: FrozenSet[Author]

from typing import List

from pydantic import BaseModel


class Author(BaseModel):
    firstname: str
    lastname: str


class Source(BaseModel):
    doi: str
    prime_id: str
    publication_year: int
    title: str
    journal_name: str
    journal_volume: str
    page_numbers: str
    authors: List[Author]

from pydantic import Field

from backend.models.model import Model


class Author(Model):
    firstname: str
    lastname: str


class Source(Model):
    doi: str
    publication_year: int
    title: str
    journal_name: str
    journal_volume: str
    page_numbers: str
    authors: list[Author] = Field(min_items=1)
    prime_id: str | None = None

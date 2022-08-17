from dataclasses import Field
from pydantic import UUID4
from pydantic import BaseModel
from frozendict import frozendict


class Model(BaseModel):
    id: UUID4

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        return frozendict(**d)

    class Config:
        frozen = True

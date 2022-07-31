from pydantic import BaseModel
from pydantic.dataclasses import dataclass


def model(*args, **kwargs):
    return dataclass(*args, frozen=True, **kwargs)

class Model(BaseModel):
    class Config:
        frozen = True

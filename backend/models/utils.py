from pydantic.dataclasses import dataclass
from dataclasses import dataclass


def frozen_dataclass(*args, **kwargs):
    return dataclass(*args, frozen=True, **kwargs)

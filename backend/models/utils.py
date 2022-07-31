from dataclasses import dataclass

from pydantic.dataclasses import dataclass


def frozen_dataclass(*args, **kwargs):
    return dataclass(*args, frozen=True, **kwargs)

import functools
from typing import Any, Callable, Dict, Iterable
from apischema import serialize
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from backend.api.db import get_db

from backend.database import Database
from backend.models.kinetic_model import KineticModel

router = APIRouter()


def serializer(serializer: Callable[[Any], Dict]):
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> JSONResponse:
            result = func(*args, **kwargs)
            return serializer(result)
        return wrapper
    return decorator


@router.post("/kinetic_model")
@serializer(serializer=serialize)
def create_kinetic_model(kinetic_model: KineticModel, db: Database = Depends(get_db)) -> KineticModel:
    db.import_kinetic_model(kinetic_model)
    return kinetic_model


@router.get("/kinetic_model/{kinetic_model_id}")
@serializer(serializer=serialize)
def get_kinetic_model(kinetic_model_id: int, db: Database = Depends(get_db)) -> KineticModel:
    try:
        return db.kinetic_models[kinetic_model_id]
    except IndexError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/kinetic_model", response_model=Iterable[KineticModel])
@serializer(serializer=serialize)
def get_kinetic_models(db: Database = Depends(get_db)) -> Iterable[KineticModel]:
    return db.kinetic_models

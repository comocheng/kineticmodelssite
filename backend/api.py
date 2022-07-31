from typing import Iterable, List
from fastapi import Depends, FastAPI

from backend.database import ObjectDatabase
from backend.database.database import Database
from backend.models.kinetic_model import KineticModel
from backend.models.source import Source

app = FastAPI()

database = ObjectDatabase()

def get_db() -> Database:
    return database

@app.post("/kinetic_model", response_model=KineticModel)
def create_kinetic_model(kinetic_model: KineticModel, db: Database = Depends(get_db)) -> KineticModel:
    db.import_kinetic_model(kinetic_model)
    return kinetic_model


# @app.post("/source", response_model=Source)
# def create_kinetic_model(source: Source) -> Source:
#     db = get_db()
#     db.import_source(source)
#     return source


# @app.get("/source", response_model=Source)
# def create_kinetic_model(kinetic_model: Source) -> Source:
#     db = get_db()
#     db.import_kinetic_model(kinetic_model)
#     return kinetic_model


@app.get("/kinetic_model/{kinetic_model_id}", response_model=KineticModel)
def get_kinetic_model(kinetic_model_id: int, db: Database = Depends(get_db)) -> KineticModel:
    return db.kinetic_models[kinetic_model_id]


@app.get("/kinetic_model", response_model=Iterable[KineticModel])
def get_kinetic_models(db: Database = Depends(get_db)) -> Iterable[KineticModel]:
    return list(db.kinetic_models)

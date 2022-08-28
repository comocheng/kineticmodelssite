from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.kinetic_model import KineticModel

router = APIRouter()


@router.post("/kinetic_model", response_model=KineticModel)
def create_kinetic_model(
    kinetic_model: KineticModel, db: Database = Depends(get_db)
) -> KineticModel:
    db.import_kinetic_model(kinetic_model)
    return kinetic_model


@router.get("/kinetic_model/{kinetic_model_id}", response_model=KineticModel)
def get_kinetic_model(kinetic_model_id: UUID, db: Database = Depends(get_db)) -> KineticModel:
    try:
        return db.get_kinetic_model(kinetic_model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/kinetic_model", response_model=list[KineticModel])
def get_kinetic_models(db: Database = Depends(get_db)) -> list[KineticModel]:
    return list(db.get_all_kinetic_models())

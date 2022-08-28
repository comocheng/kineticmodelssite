
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.kinetics import Kinetics

router = APIRouter()


@router.post("/kinetics", response_model=Kinetics)
def create_kinetics(kinetics: Kinetics, db: Database = Depends(get_db)) -> Kinetics:
    db.import_kinetics(kinetics)
    return kinetics


@router.get("/kinetics/{kinetics_id}", response_model=Kinetics)
def get_kinetics(kinetics_id: UUID, db: Database = Depends(get_db)) -> Kinetics:
    try:
        return db.get_kinetics(kinetics_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/kinetics", response_model=list[Kinetics])
def get_kineticss(db: Database = Depends(get_db)) -> list[Kinetics]:
    return list(db.get_all_kinetics())

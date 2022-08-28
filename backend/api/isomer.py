from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.species import Isomer

router = APIRouter()


@router.post("/isomer", response_model=Isomer)
def create_isomer(isomer: Isomer, db: Database = Depends(get_db)) -> Isomer:
    db.import_isomer(isomer)
    return isomer


@router.get("/isomer/{isomer_id}", response_model=Isomer)
def get_isomer(isomer_id: UUID, db: Database = Depends(get_db)) -> Isomer:
    try:
        return db.get_isomer(isomer_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/isomer", response_model=list[Isomer])
def get_isomers(db: Database = Depends(get_db)) -> list[Isomer]:
    return list(db.get_all_isomers())

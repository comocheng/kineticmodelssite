from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.thermo import Thermo

router = APIRouter()


@router.post("/thermo", response_model=Thermo)
def create_thermo(thermo: Thermo, db: Database = Depends(get_db)) -> Thermo:
    db.import_thermo(thermo)
    return thermo


@router.get("/thermo/{thermo_id}", response_model=Thermo)
def get_thermo(thermo_id: UUID, db: Database = Depends(get_db)) -> Thermo:
    try:
        return db.get_thermo(thermo_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/thermo", response_model=Iterable[Thermo])
def get_thermos(db: Database = Depends(get_db)) -> Iterable[Thermo]:
    return db.get_all_thermo()

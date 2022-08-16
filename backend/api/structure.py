from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.species import Structure

router = APIRouter()


@router.post("/structure", response_model=Structure)
def create_structure(structure: Structure, db: Database = Depends(get_db)) -> Structure:
    db.import_structure(structure)
    return structure


@router.get("/structure/{structure_id}", response_model=Structure)
def get_structure(structure_id: UUID, db: Database = Depends(get_db)) -> Structure:
    try:
        return db.get_structure(structure_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/structure", response_model=Iterable[Structure])
def get_structures(db: Database = Depends(get_db)) -> Iterable[Structure]:
    return db.get_all_structures()

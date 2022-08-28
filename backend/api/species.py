
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.species import Species

router = APIRouter()


@router.post("/species", response_model=Species)
def create_species(species: Species, db: Database = Depends(get_db)) -> Species:
    db.import_species(species)
    return species


@router.get("/species/{species_id}", response_model=Species)
def get_species(species_id: UUID, db: Database = Depends(get_db)) -> Species:
    try:
        return db.get_species(species_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/species", response_model=list[Species])
def get_all_species(db: Database = Depends(get_db)) -> list[Species]:
    return list(db.get_all_species())

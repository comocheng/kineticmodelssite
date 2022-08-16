from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.reaction import Reaction

router = APIRouter()


@router.post("/reaction", response_model=Reaction)
def create_reaction(reaction: Reaction, db: Database = Depends(get_db)) -> Reaction:
    db.import_reaction(reaction)
    return reaction


@router.get("/reaction/{reaction_id}", response_model=Reaction)
def get_reaction(reaction_id: UUID, db: Database = Depends(get_db)) -> Reaction:
    try:
        return db.get_reaction(reaction_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/reaction", response_model=Iterable[Reaction])
def get_reactions(db: Database = Depends(get_db)) -> Iterable[Reaction]:
    return db.get_all_reactions()

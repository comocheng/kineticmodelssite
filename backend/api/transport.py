from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_db
from backend.database import Database
from backend.models.transport import Transport

router = APIRouter()


@router.post("/transport", response_model=Transport)
def create_transport(transport: Transport, db: Database = Depends(get_db)) -> Transport:
    db.import_transport(transport)
    return transport


@router.get("/transport/{transport_id}", response_model=Transport)
def get_transport(transport_id: UUID, db: Database = Depends(get_db)) -> Transport:
    try:
        return db.get_transport(transport_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/transport", response_model=Iterable[Transport])
def get_transports(db: Database = Depends(get_db)) -> Iterable[Transport]:
    return db.get_all_transport()

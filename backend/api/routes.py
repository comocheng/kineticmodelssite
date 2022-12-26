from fastapi import APIRouter, Depends, HTTPException

from backend.api.db import get_event_model
from backend.database.event_model import EventModel
from backend.database.event_store import EventStore
from backend.models.kinetic_model import KineticModel
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport

router = APIRouter()


@router.post("/kinetic_model", response_model=KineticModel)
def create_kinetic_model(
    kinetic_model: KineticModel, store: EventStore = Depends(get_event_model)
) -> KineticModel:
    store.append_kinetic_model(kinetic_model)
    return kinetic_model


@router.get("/kinetic_model/{kinetic_model_id}", response_model=KineticModel)
def get_kinetic_model(kinetic_model_id: int, model: EventModel = Depends(get_event_model)) -> KineticModel:
    match km := model.get_kinetic_model(kinetic_model_id):
        case KineticModel():
            return km
        case None:
            raise HTTPException(status_code=404, detail="Model not found")


@router.get("/kinetic_model", response_model=list[KineticModel])
def get_kinetic_models(model: EventModel = Depends(get_event_model)) -> list[KineticModel]:
    return list(model.get_kinetic_models())


@router.get("/kinetics", response_model=list[KineticModel])
def get_kinetic_models(model: EventModel = Depends(get_event_model)) -> list[KineticModel]:
    return list(model.get_all_kinetic_models())


@router.get("/thermo", response_model=list[Thermo])
def get_kinetic_models(model: EventModel = Depends(get_event_model)) -> list[KineticModel]:
    return list(model.get_thermo())


@router.get("/transport", response_model=list[Transport])
def get_kinetic_models(model: EventModel = Depends(get_event_model)) -> list[KineticModel]:
    return list(model.get_transport())


@router.get("/species", response_model=list[Species])
def get_kinetic_models(model: EventModel = Depends(get_event_model)) -> list[KineticModel]:
    return list(model.get_species())


@router.get("/isomer", response_model=list[Isomer])
def get_kinetic_models(model: EventModel = Depends(get_event_model)) -> list[KineticModel]:
    return list(model.get_isomers())


@router.get("/structure", response_model=list[Structure])
def get_kinetic_models(model: EventModel = Depends(get_event_model)) -> list[KineticModel]:
    return list(model.get_structures())

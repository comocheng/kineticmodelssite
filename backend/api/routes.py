from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from backend.api.resources import get_event_source, get_model_repo
from backend.database.event_source import EventSource
from backend.database.model_repository import ModelRepository
from backend.models.kinetic_model import KineticModel
from backend.models.kinetics import Kinetics
from backend.models.species import Isomer, Species, Structure
from backend.models.thermo import Thermo
from backend.models.transport import Transport

router = APIRouter()


@router.post("/kinetic_model", response_model=KineticModel)
def create_kinetic_model(
    kinetic_model: KineticModel, source: EventSource = Depends(get_event_source)
) -> KineticModel:
    source.update(kinetic_model)
    return kinetic_model


@router.get("/kinetic_model/{id}", response_model=KineticModel)
def get_kinetic_model(id: UUID, repo: ModelRepository = Depends(get_model_repo)) -> KineticModel:
    match km := repo.get_kinetic_model(id):
        case KineticModel():
            return km
        case None:
            raise HTTPException(status_code=404, detail="Model not found")


@router.get("/kinetic_model", response_model=list[KineticModel])
def get_kinetic_models(repo: ModelRepository = Depends(get_model_repo)) -> list[KineticModel]:
    return repo.kinetic_models


@router.get("/kinetics", response_model=list[Kinetics])
def get_kinetic_models(repo: ModelRepository = Depends(get_model_repo)) -> list[Kinetics]:
    return repo.kinetics


@router.get("/thermo", response_model=list[Thermo])
def get_kinetic_models(repo: ModelRepository = Depends(get_model_repo)) -> list[Thermo]:
    return repo.thermo


@router.get("/transport", response_model=list[Transport])
def get_kinetic_models(repo: ModelRepository = Depends(get_model_repo)) -> list[Transport]:
    return repo.transport


@router.get("/species", response_model=list[Species])
def get_kinetic_models(repo: ModelRepository = Depends(get_model_repo)) -> list[Species]:
    return repo.species


@router.get("/isomer", response_model=list[Isomer])
def get_kinetic_models(repo: ModelRepository = Depends(get_model_repo)) -> list[Isomer]:
    return repo.isomers


@router.get("/structure", response_model=list[Structure])
def get_kinetic_models(repo: ModelRepository = Depends(get_model_repo)) -> list[Structure]:
    return repo.structures

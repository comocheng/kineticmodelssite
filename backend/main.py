from fastapi import FastAPI

from backend.api import (
    isomer,
    kinetic_model,
    kinetics,
    reaction,
    species,
    structure,
    thermo,
    transport,
)

app = FastAPI()

app.include_router(kinetic_model.router)
app.include_router(kinetics.router)
app.include_router(thermo.router)
app.include_router(transport.router)
app.include_router(reaction.router)
app.include_router(species.router)
app.include_router(isomer.router)
app.include_router(structure.router)

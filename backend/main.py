from fastapi import FastAPI

from backend.api import kinetic_model

app = FastAPI()

app.include_router(kinetic_model.router)

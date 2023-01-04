from fastapi import FastAPI

from backend.api import routes

app = FastAPI()

app.include_router(routes.router)

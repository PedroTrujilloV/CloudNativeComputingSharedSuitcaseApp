from fastapi import FastAPI

from config import Settings
from entrypoints.api.routers.pet_router import router as pet_router

app = FastAPI(title=Settings.app_name)
app.include_router(pet_router)

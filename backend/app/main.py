from fastapi import FastAPI

from app.routers.health import router as health_router
from app.routers.legal import router as legal_router


app = FastAPI(title="Legal AI Agent Backend", version="0.1.0")
app.include_router(health_router)
app.include_router(legal_router)


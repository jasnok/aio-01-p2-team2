from fastapi import FastAPI

from backend.app.routers.health import router as health_router
from backend.app.routers.integration_router import router as integration_router
from backend.app.routers.legal import router as legal_router


app = FastAPI(title="Legal AI Agent Backend", version="0.1.0")
app.include_router(health_router)
app.include_router(legal_router)
app.include_router(integration_router)

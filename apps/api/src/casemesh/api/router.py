from fastapi import APIRouter

from casemesh.api.routes.cases import router as cases_router
from casemesh.api.routes.documents import router as documents_router
from casemesh.api.routes.health import router as health_router
from casemesh.api.routes.readiness import router as readiness_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(readiness_router)
api_router.include_router(cases_router)
api_router.include_router(documents_router)

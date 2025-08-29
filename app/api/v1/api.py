"""
Main API router for v1 endpoints.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, billing, payments, upload, core, projects

api_router = APIRouter()

# Include authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Include billing endpoints
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])

# Include payment endpoints
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])

# Include upload endpoints
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])

# Include core processing endpoints
api_router.include_router(core.router, tags=["core"])

# Include project management endpoints
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

@api_router.get("/ping")
async def ping():
    return {"message": "pong"}
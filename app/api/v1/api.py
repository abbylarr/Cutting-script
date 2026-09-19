"""
Main API router for v1 endpoints.
"""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, billing, payments, upload, core, projects

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])

# Upload routes are absolute under /api/v1 (see upload.router paths)
api_router.include_router(upload.router, tags=["upload"])

api_router.include_router(core.router, tags=["core"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

# FE alias: POST /api/v1/save/{task_id}
from app.api.v1.endpoints.projects import save_project_changes  # noqa: E402

api_router.add_api_route(
    "/save/{task_id}",
    save_project_changes,
    methods=["POST"],
    tags=["projects"],
)


@api_router.get("/ping")
async def ping():
    return {"message": "pong"}

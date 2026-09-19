"""
Main FastAPI application entry point for filmlist service.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.error_handlers import setup_error_handlers
from app.core.logging import get_logger

logger = get_logger("main")

app = FastAPI(
    title="Filmlist API",
    description="Автоматическое создание монтажных листов. Работает автономно без OpenAI-ключа (fallback).",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

setup_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
async def startup_event():
    logger.info(
        "Filmlist API starting",
        extra={
            "version": "1.0.0",
            "autonomous": settings.AUTONOMOUS_MODE,
            "has_openai": settings.has_openai,
        },
    )

    try:
        from app.db.base import init_db
        init_db()
        logger.info("Database tables ensured")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    try:
        from app.services.task_queue import task_queue
        await task_queue.start()
        logger.info("Task queue started")
    except Exception as e:
        logger.error(f"Failed to start task queue: {e}")

    try:
        from app.core.health_monitor import setup_health_monitoring
        await setup_health_monitoring()
        logger.info("Health monitoring initialized")
    except Exception as e:
        logger.warning(f"Health monitoring skipped: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Filmlist API shutting down")
    try:
        from app.services.task_queue import task_queue
        await task_queue.stop()
    except Exception as e:
        logger.warning(f"Task queue stop failed: {e}")

    try:
        from app.core.health_monitor import cleanup_health_monitoring
        await cleanup_health_monitoring()
    except Exception as e:
        logger.warning(f"Health monitor cleanup failed: {e}")

    try:
        from app.core.redis import cache_manager
        await cache_manager.close()
    except Exception:
        pass


@app.get("/")
async def root():
    return {
        "message": "Filmlist API",
        "version": "1.0.0",
        "autonomous_mode": settings.AUTONOMOUS_MODE,
        "openai_enabled": settings.has_openai,
        "docs": f"{settings.API_V1_STR}/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "autonomous_mode": settings.AUTONOMOUS_MODE,
        "openai_enabled": settings.has_openai,
    }


@app.get("/health/detailed")
async def detailed_health_check():
    try:
        from app.core.health_monitor import health_monitor
        from app.services.fallback_services import fallback_services
        from app.core.redis import cache_manager

        services_status = {}
        try:
            services_status = health_monitor.get_all_services_status()
        except Exception:
            services_status = {}

        redis_ok = await cache_manager.health_check()
        services_status["redis"] = {
            "status": "healthy" if redis_ok else "degraded",
            "note": "in-memory fallback OK" if redis_ok else "unavailable",
        }
        services_status["openai"] = {
            "status": "healthy" if settings.has_openai else "fallback",
            "note": "using offline fallbacks" if not settings.has_openai else "configured",
        }

        try:
            fallback_status = await fallback_services.get_service_status()
        except Exception:
            fallback_status = {}

        return {
            "status": "healthy",
            "version": "1.0.0",
            "autonomous_mode": settings.AUTONOMOUS_MODE,
            "services": services_status,
            "fallback_services": fallback_status,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "error", "error": str(e)}

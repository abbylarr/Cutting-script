"""
Main FastAPI application entry point for filmlist service.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.error_handlers import setup_error_handlers
from app.core.logging import get_logger

# Initialize logging
logger = get_logger("main")

app = FastAPI(
    title="Filmlist API",
    description="""
    ## Автоматическое создание монтажных листов из видеофайлов
    
    Filmlist - это веб-сервис для автоматического создания монтажных листов из видеофайлов 
    в соответствии с требованиями Госфильмфонда РФ.
    
    ### Основные возможности:
    - 🎬 **Автоматическая обработка видео** - загрузите видеофайл и получите готовый монтажный лист
    - 🎤 **Транскрипция речи** - автоматическое распознавание речи с помощью OpenAI Whisper
    - 👥 **Диаризация спикеров** - автоматическое определение и разделение голосов
    - 🖼️ **Визуальный анализ** - ИИ-анализ кадров с определением типов планов
    - 📝 **Интерактивное редактирование** - возможность корректировки результатов
    - 📄 **Генерация DOCX** - создание документов по стандартам Госфильмфонда
    
    ### Поддерживаемые форматы:
    - MP4, AVI, MOV, MKV, WEBM
    - Максимальный размер файла: 5 ГБ
    - Максимальная длительность: 3 часа
    
    ### Тарифы:
    - **Автотранскрипция**: 75 ₽ за минуту видео
    - **С SRT файлом**: 25 ₽ за минуту видео
    
    ### Документация:
    - [Руководство пользователя](https://docs.filmlist.ru/user-guide)
    - [Руководство разработчика](https://docs.filmlist.ru/developer-guide)
    - [FAQ](https://docs.filmlist.ru/faq)
    
    ### Поддержка:
    - Email: support@filmlist.ru
    - Чат на сайте: [filmlist.ru](https://filmlist.ru)
    """,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    contact={
        "name": "Filmlist Support",
        "email": "support@filmlist.ru",
        "url": "https://filmlist.ru/support"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://filmlist.ru/license"
    },
    servers=[
        {
            "url": "https://api.filmlist.ru",
            "description": "Production server"
        },
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        }
    ]
)

# Setup error handlers
setup_error_handlers(app)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("Filmlist API starting up", extra={
        "version": "1.0.0",
        "api_prefix": settings.API_V1_STR
    })
    
    # Initialize health monitoring for external services
    try:
        from app.core.health_monitor import setup_health_monitoring
        await setup_health_monitoring()
        logger.info("Health monitoring initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize health monitoring: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Filmlist API shutting down")
    
    # Cleanup health monitoring
    try:
        from app.core.health_monitor import cleanup_health_monitoring
        await cleanup_health_monitoring()
        logger.info("Health monitoring cleanup completed")
    except Exception as e:
        logger.error(f"Failed to cleanup health monitoring: {e}")

@app.get("/")
async def root():
    return {"message": "Filmlist API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check including external services."""
    try:
        from app.core.health_monitor import health_monitor
        from app.services.fallback_services import fallback_services
        
        # Get health status of all monitored services
        services_status = health_monitor.get_all_services_status()
        
        # Get fallback services status
        fallback_status = await fallback_services.get_service_status()
        
        # Determine overall health
        overall_status = "healthy"
        critical_services = ["database", "redis"]
        
        for service_name, service_info in services_status.items():
            if service_info and service_info.get("status") == "unhealthy":
                if service_name in critical_services:
                    overall_status = "unhealthy"
                elif overall_status == "healthy":
                    overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": logger._context.get("timestamp", "unknown"),
            "version": "1.0.0",
            "services": services_status,
            "fallback_services": fallback_status
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": logger._context.get("timestamp", "unknown")
        }
"""
Database base configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Import all models here so Alembic can detect them
from app.models.user import User  # noqa
from app.models.processing_task import ProcessingTask  # noqa
from app.models.film_project import FilmProject  # noqa
from app.models.transaction import Transaction  # noqa
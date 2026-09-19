"""
Database base configuration and session management.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (useful for SQLite / autonomous mode without Alembic)."""
    # Import models so metadata is populated
    from app.models.user import User  # noqa: F401
    from app.models.processing_task import ProcessingTask  # noqa: F401
    from app.models.film_project import FilmProject  # noqa: F401
    from app.models.transaction import Transaction  # noqa: F401
    Base.metadata.create_all(bind=engine)


# Import all models here so Alembic can detect them
from app.models.user import User  # noqa: E402,F401
from app.models.processing_task import ProcessingTask  # noqa: E402,F401
from app.models.film_project import FilmProject  # noqa: E402,F401
from app.models.transaction import Transaction  # noqa: E402,F401

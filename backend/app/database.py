from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings

settings = get_settings()
db_url = settings.resolved_database_url

# Ensure the data directory exists
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    if not db_path.startswith(":memory:"):
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

# Create engine with check_same_thread=False for SQLite multi-thread safety
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False,
)

# Enforce foreign key constraints on SQLite connections
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that yields a SQLAlchemy database session and guarantees cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

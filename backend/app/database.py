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


def init_db():
    """Initializes tables and performs safe, non-destructive schema migrations."""
    import app.models.user  # noqa: F401
    import app.models.invoice  # noqa: F401
    import app.models.payment  # noqa: F401
    import app.models.anomaly  # noqa: F401
    import app.models.reconciliation  # noqa: F401
    from sqlalchemy import text, inspect

    Base.metadata.create_all(bind=engine)

    try:
        insp = inspect(engine)
        if "payments" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("payments")]
            with engine.connect() as conn:
                if "verification_status" not in cols:
                    conn.execute(text("ALTER TABLE payments ADD COLUMN verification_status VARCHAR(50) DEFAULT 'UNVERIFIED' NOT NULL"))
                if "evidence_source" not in cols:
                    conn.execute(text("ALTER TABLE payments ADD COLUMN evidence_source VARCHAR(100) DEFAULT 'MANUAL_ENTRY' NOT NULL"))
                if "matched_reference" not in cols:
                    conn.execute(text("ALTER TABLE payments ADD COLUMN matched_reference VARCHAR(100)"))
                if "mismatch_reason" not in cols:
                    conn.execute(text("ALTER TABLE payments ADD COLUMN mismatch_reason TEXT"))
                conn.commit()
        if "payment_audit_logs" in insp.get_table_names():
            pal_cols = [c["name"] for c in insp.get_columns("payment_audit_logs")]
            with engine.connect() as conn:
                if "verification_status" not in pal_cols:
                    conn.execute(text("ALTER TABLE payment_audit_logs ADD COLUMN verification_status VARCHAR(50)"))
                conn.commit()
    except Exception:
        pass


def get_db():
    """Dependency that yields a SQLAlchemy database session and guarantees cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

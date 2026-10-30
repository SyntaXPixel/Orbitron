from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.config import settings

class Base(DeclarativeBase):
    pass

resolved_db_url = settings.get_resolved_database_url()

engine = create_engine(
    resolved_db_url,
    connect_args={"check_same_thread": False} if resolved_db_url.startswith("sqlite") else {},
    echo=False
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if resolved_db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

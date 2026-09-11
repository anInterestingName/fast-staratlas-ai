from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def create_db_engine(url: str | None = None) -> Engine:
    return create_engine(url or settings.database_url, pool_pre_ping=True)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ping_database(session: Session) -> None:
    session.execute(text("SELECT 1"))

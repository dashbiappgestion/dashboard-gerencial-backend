from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings, reload_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    reload_settings()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={
                "sslmode": "require",
                "options": "-c search_path=public",
                "connect_timeout": 15,
            },
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> dict:
    settings = get_settings()
    try:
        with get_engine().connect() as conn:
            regions = conn.execute(text("SELECT COUNT(*) FROM dim_region")).scalar()
        return {
            "ok": True,
            "host": settings.db_host,
            "port": settings.db_port,
            "user": settings.db_user,
            "regions": regions,
        }
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "host": settings.db_host,
            "port": settings.db_port,
            "user": settings.db_user,
            "error": str(exc.__cause__ or exc),
        }


def fetch_all(session: Session, query: str, params: dict | None = None) -> list[dict]:
    result = session.execute(text(query), params or {})
    return [dict(row._mapping) for row in result]


def fetch_one(session: Session, query: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(session, query, params)
    return rows[0] if rows else None

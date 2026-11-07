"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engines: dict[str, Engine] = {}


def get_engine(url: str) -> Engine:
    engine = _engines.get(url)
    if engine is None:
        engine = create_engine(url, pool_pre_ping=True, future=True)
        _engines[url] = engine
    return engine


def session_factory(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False, future=True)


def iter_session(factory: sessionmaker[Session]) -> Iterator[Session]:
    db = factory()
    try:
        yield db
    finally:
        db.close()

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from projektstyring.backend.config import require_env


DATABASE_URL = require_env("PROJEKTSTYRING_DATABASE_URL")


engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    pass


def get_session():
    with SessionLocal() as session:
        yield session
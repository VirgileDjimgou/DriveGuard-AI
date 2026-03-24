from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from driver_monitoring.backend.models import Base
from driver_monitoring.config import AppConfig, load_app_config


@dataclass(frozen=True)
class DatabaseRuntime:
    config_path: str
    engine: Engine
    session_factory: sessionmaker[Session]


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        relative_path = database_url.removeprefix("sqlite:///")
        if relative_path == ":memory:":
            return database_url
        return f"sqlite:///{Path(relative_path).resolve()}"
    return database_url


@lru_cache(maxsize=8)
def get_database_runtime(config_path: str = "config.toml") -> DatabaseRuntime:
    app_config = load_app_config(config_path)
    database_url = _normalize_database_url(app_config.backend.database_url)
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, future=True, connect_args=connect_args)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return DatabaseRuntime(config_path=config_path, engine=engine, session_factory=session_factory)


def init_database(config_path: str = "config.toml") -> None:
    runtime = get_database_runtime(config_path)
    Base.metadata.create_all(runtime.engine)


@contextmanager
def session_scope(config_path: str = "config.toml") -> Iterator[Session]:
    runtime = get_database_runtime(config_path)
    session = runtime.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_backend_config(config_path: str = "config.toml") -> AppConfig:
    return load_app_config(config_path)

"""Connection adapter: SQLite by default, PostgreSQL when DATABASE_URL is set.

Callers keep using `?` placeholders and dict-like rows. Timestamps from
Postgres are returned as ISO strings so existing services stay unchanged.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from app.core.config import settings

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.errors import IntegrityError as PostgresIntegrityError
except ImportError:  # optional until pip install -e .
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    PostgresIntegrityError = None  # type: ignore[misc, assignment]


IntegrityConflict: tuple[type[Exception], ...] = (sqlite3.IntegrityError,)
if PostgresIntegrityError is not None:
    IntegrityConflict = (sqlite3.IntegrityError, PostgresIntegrityError)

DatabaseError: tuple[type[Exception], ...] = (sqlite3.Error,)
if psycopg is not None:
    DatabaseError = (sqlite3.Error, psycopg.Error)


def uses_postgres() -> bool:
    return bool((settings.database_url or "").strip())


def storage_dialect() -> str:
    return "postgresql" if uses_postgres() else "sqlite"


def _adapt_sql(sql: str) -> str:
    if not uses_postgres():
        return sql
    return sql.replace("?", "%s")


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    return {key: _normalize_value(value) for key, value in data.items()}


class CursorWrapper:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def fetchone(self) -> dict[str, Any] | None:
        return _normalize_row(self._cursor.fetchone())

    def fetchall(self) -> list[dict[str, Any]]:
        return [row for row in (_normalize_row(item) for item in self._cursor.fetchall()) if row is not None]


class DbConnection:
    def __init__(self, raw: Any) -> None:
        self._raw = raw
        self.dialect = storage_dialect()

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> CursorWrapper:
        adapted = _adapt_sql(sql)
        if params is None:
            cursor = self._raw.execute(adapted)
        else:
            cursor = self._raw.execute(adapted, tuple(params))
        return CursorWrapper(cursor)

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]) -> CursorWrapper:
        adapted = _adapt_sql(sql)
        params = list(seq_of_params)
        if self.dialect == "postgresql":
            # psycopg Connection has execute(), not executemany(); that method is on the cursor.
            cursor = self._raw.cursor()
            cursor.executemany(adapted, params)
            return CursorWrapper(cursor)
        return CursorWrapper(self._raw.executemany(adapted, params))

    def executescript(self, script: str) -> None:
        if self.dialect == "postgresql":
            raise RuntimeError("executescript is SQLite-only; use postgres schema statements.")
        self._raw.executescript(script)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()

    def __enter__(self) -> DbConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def get_connection() -> DbConnection:
    if uses_postgres():
        if psycopg is None:
            raise RuntimeError("psycopg is required when AURAVANCE_DATABASE_URL is set.")
        raw = psycopg.connect(settings.database_url, row_factory=dict_row)
        return DbConnection(raw)

    path = Path(settings.demo_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    raw.execute("PRAGMA journal_mode=WAL")
    return DbConnection(raw)

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from backend.app.db.session import (
    get_session_factory,
)


def get_db_session() -> Iterator[Session]:
    session_factory = (
        get_session_factory()
    )

    with session_factory() as session:
        yield session

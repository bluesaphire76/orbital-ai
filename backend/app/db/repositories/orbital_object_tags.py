from __future__ import annotations

from typing import Iterable

from sqlalchemy.dialects.postgresql import (
    insert,
)
from sqlalchemy.orm import Session

from backend.app.db.models.orbital_object_tag import (
    OrbitalObjectTag,
)


class OrbitalObjectTagRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session


    def add_many(
        self,
        rows: Iterable[
            dict[str, object]
        ],
        *,
        batch_size: int = 5000,
    ) -> int:
        prepared = list(
            rows
        )

        inserted = 0


        for offset in range(
            0,
            len(prepared),
            batch_size,
        ):
            batch = prepared[
                offset:
                offset + batch_size
            ]

            if not batch:
                continue


            statement = (
                insert(
                    OrbitalObjectTag
                )
                .values(
                    batch
                )
                .on_conflict_do_nothing(
                    constraint=
                        "uq_orbital_object_tag"
                )
                .returning(
                    OrbitalObjectTag.id
                )
            )


            inserted += len(
                self._session
                .scalars(
                    statement
                )
                .all()
            )


        return inserted

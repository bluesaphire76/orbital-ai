from __future__ import annotations

from sqlalchemy import (
    func,
    select,
)

from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.satcat_sync import (
    sync_satcat_records,
)
from ingestion.celestrak_satcat import (
    fetch_satcat_csv,
)


def main() -> None:
    records, from_cache = (
        fetch_satcat_csv()
    )

    print(
        "SATCAT source:",
        "cache"
        if from_cache
        else "CelesTrak",
    )

    print(
        "SATCAT records fetched:",
        len(records),
    )


    session_factory = (
        get_session_factory()
    )


    with session_factory() as session:
        result = (
            sync_satcat_records(
                session,
                records,
            )
        )


        print()
        print(
            "=== SATCAT SYNC ==="
        )

        print(
            "records:",
            result.records,
        )

        print(
            "created:",
            result.created,
        )

        print(
            "updated:",
            result.updated,
        )

        print()
        print(
            "payloads:",
            result.payloads,
        )

        print(
            "rocket_bodies:",
            result.rocket_bodies,
        )

        print(
            "debris:",
            result.debris,
        )

        print(
            "unknown:",
            result.unknown,
        )

        print(
            "other:",
            result.other,
        )

        print()
        print(
            "on_orbit:",
            result.on_orbit,
        )

        print(
            "decayed:",
            result.decayed,
        )


        print()
        print(
            "=== DATABASE ==="
        )


        total = session.scalar(
            select(
                func.count()
            )
            .select_from(
                OrbitalObject
            )
        )

        current_elements = (
            session.scalar(
                select(
                    func.count()
                )
                .select_from(
                    OrbitalObject
                )
                .where(
                    OrbitalObject
                    .has_current_elements
                    .is_(True)
                )
            )
        )


        print(
            "database_total:",
            total,
        )

        print(
            "with_current_elements:",
            current_elements,
        )


if __name__ == "__main__":
    main()

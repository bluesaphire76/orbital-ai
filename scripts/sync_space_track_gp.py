from __future__ import annotations

from backend.app.observability.operations import observe_ingestion

from sqlalchemy import (
    func,
    select,
)

from backend.app.db.models.orbital_element import (
    OrbitalElement,
)
from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.space_track_sync import (
    sync_space_track_gp,
)
from ingestion.providers.space_track import (
    fetch_current_gp,
)


@observe_ingestion("space-track")
def main() -> None:
    records, cached = (
        fetch_current_gp()
    )


    print(
        "Space-Track source:",
        "cache"
        if cached
        else "network",
    )

    print(
        "GP records fetched:",
        len(records),
    )


    session_factory = (
        get_session_factory()
    )


    with session_factory() as session:
        result = (
            sync_space_track_gp(
                session,
                records,
            )
        )


        print()
        print(
            "=== SPACE-TRACK GP SYNC ==="
        )

        print(
            "records:",
            result.records,
        )

        print(
            "matched_objects:",
            result.matched_objects,
        )

        print(
            "unmatched_objects:",
            result.unmatched_objects,
        )

        print(
            "elements_created:",
            result.elements_created,
        )

        print(
            "elements_existing:",
            result.elements_existing,
        )


        space_track_objects = (
            session.scalar(
                select(
                    func.count(
                        func.distinct(
                            OrbitalElement
                            .orbital_object_id
                        )
                    )
                )
                .where(
                    OrbitalElement.source
                    == "space-track"
                )
            )
            or 0
        )


        earth_with_elements = (
            session.scalar(
                select(
                    func.count()
                )
                .select_from(
                    OrbitalObject
                )
                .where(
                    OrbitalObject
                    .is_earth_orbit
                    .is_(True),

                    OrbitalObject
                    .has_current_elements
                    .is_(True),
                )
            )
            or 0
        )


        print()
        print(
            "=== DATABASE ==="
        )

        print(
            "space_track_objects:",
            space_track_objects,
        )

        print(
            "earth_with_elements:",
            earth_with_elements,
        )


if __name__ == "__main__":
    main()

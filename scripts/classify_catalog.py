from __future__ import annotations

from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.catalog_classification import (
    GROUP_CLASSIFICATIONS,
    apply_group_tags,
    count_current_elements,
    count_tagged_objects,
    seed_object_type_tags,
)
from backend.app.services.celestrak_sync import (
    sync_celestrak_records,
)
from ingestion.celestrak import (
    fetch_gp_by_group,
)


def main() -> None:
    session_factory = (
        get_session_factory()
    )


    with session_factory() as session:
        inserted = (
            seed_object_type_tags(
                session
            )
        )

        print(
            "object-type tags inserted:",
            inserted,
        )

        print()
        print(
            "=== CELESTRAK GROUP CLASSIFICATION ==="
        )


        for definition in (
            GROUP_CLASSIFICATIONS
        ):
            records, cached = (
                fetch_gp_by_group(
                    definition.group
                )
            )


            sync_result = (
                sync_celestrak_records(
                    session,
                    records,
                )
            )


            objects, tags = (
                apply_group_tags(
                    session,
                    group=
                        definition.group,

                    records=
                        records,

                    tags=
                        definition.tags,
                )
            )


            print(
                f"{definition.group:14}",
                f"objects={objects:6}",
                f"tags+={tags:6}",
                "cache"
                if cached
                else "network",
                f"elements+={sync_result.elements_created}",
            )


        print()
        print(
            "=== CLASSIFICATION SUMMARY ==="
        )

        print(
            "tagged_objects:",
            count_tagged_objects(
                session
            ),
        )

        print(
            "with_current_elements:",
            count_current_elements(
                session
            ),
        )


if __name__ == "__main__":
    main()

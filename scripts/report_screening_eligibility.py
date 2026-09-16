from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.ephemeris_selection import (
    select_screening_ephemerides,
)


def main() -> None:
    now = datetime.now(
        timezone.utc
    )

    factory = (
        get_session_factory()
    )


    with factory() as session:
        selection = (
            select_screening_ephemerides(
                session,
                target_time=now,
            )
        )


    print(
        "=== SCREENING ELIGIBILITY ==="
    )

    print(
        "target_time:",
        selection
        .target_time
        .isoformat(),
    )

    print()

    print(
        "canonical_total:",
        selection.canonical_total,
    )

    print(
        "eligible_total:",
        selection.eligible_total,
    )

    print(
        "not_eligible:",
        selection.expired_total,
    )


    if selection.canonical_total:
        percentage = (
            100.0
            * selection.eligible_total
            / selection.canonical_total
        )

        print(
            "eligible_pct:",
            f"{percentage:.2f}",
        )


    print()
    print(
        "=== EPHEMERIS STATUS ==="
    )

    for status, count in sorted(
        selection
        .status_counts
        .items()
    ):
        print(
            f"{status:12}",
            count,
        )


    print()
    print(
        "=== CANONICAL SOURCES ==="
    )

    for source, count in sorted(
        selection
        .source_counts
        .items()
    ):
        print(
            f"{source:16}",
            count,
        )


    print()
    print(
        "=== ELIGIBLE SOURCES ==="
    )

    for source, count in sorted(
        selection
        .eligible_source_counts
        .items()
    ):
        print(
            f"{source:16}",
            count,
        )


    print()
    print(
        "=== ELIGIBLE OBJECT TYPES ==="
    )

    for object_type, count in sorted(
        selection
        .eligible_object_type_counts
        .items(),
        key=lambda item:
            item[1],
        reverse=True,
    ):
        print(
            f"{object_type:16}",
            count,
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

from backend.app.observability.operations import observe_ingestion

import argparse
from pathlib import Path

from backend.app.db.session import (
    get_session_factory,
)
from backend.app.services.celestrak_sync import (
    sync_celestrak_records,
)
from ingestion.celestrak import (
    fetch_gp_by_group,
    normalize_group_name,
)


DEFAULT_MAX_RECORDS = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize a controlled "
            "CelesTrak GP group into OrbitalAI."
        )
    )

    parser.add_argument(
        "--group",
        default="STATIONS",
        help=(
            "CelesTrak GP group name. "
            "Default: STATIONS"
        ),
    )

    parser.add_argument(
        "--max-records",
        type=int,
        default=DEFAULT_MAX_RECORDS,
        help=(
            "Safety limit for records returned "
            "by the selected group."
        ),
    )

    return parser.parse_args()


@observe_ingestion("celestrak")
def main() -> None:
    args = parse_args()

    if args.max_records <= 0:
        raise ValueError(
            "--max-records must be greater than zero"
        )

    group = normalize_group_name(
        args.group
    )

    records, from_cache = (
        fetch_gp_by_group(
            group,
            cache_dir=Path(
                "/tmp/orbitalai/celestrak"
            ),
        )
    )

    record_count = len(records)

    if record_count > args.max_records:
        raise RuntimeError(
            f"CelesTrak group {group} returned "
            f"{record_count} records; safety limit "
            f"is {args.max_records}. "
            "Increase --max-records explicitly "
            "only after validating the workload."
        )

    session_factory = (
        get_session_factory()
    )

    with session_factory() as session:
        result = sync_celestrak_records(
            session,
            records,
        )

    source = (
        "local cache"
        if from_cache
        else "CelesTrak"
    )

    print(f"Group: {group}")
    print(f"Source: {source}")
    print(
        f"Downloaded records: "
        f"{record_count}"
    )
    print(
        f"Processed: "
        f"{result.records}"
    )
    print(
        "Objects created: "
        f"{result.objects_created}"
    )
    print(
        "Objects updated: "
        f"{result.objects_updated}"
    )
    print(
        "Elements created: "
        f"{result.elements_created}"
    )
    print(
        "Elements existing: "
        f"{result.elements_existing}"
    )


if __name__ == "__main__":
    main()

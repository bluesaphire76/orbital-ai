from __future__ import annotations

from backend.app.observability.operations import observe_ingestion

import argparse
from pathlib import Path

from backend.app.db.session import get_session_factory
from backend.app.services.celestrak_sync import (
    sync_celestrak_records,
)
from ingestion.celestrak import fetch_gp_by_catnr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize a CelesTrak object and orbital "
            "elements into the OrbitalAI catalog."
        )
    )

    parser.add_argument(
        "--catnr",
        type=int,
        required=True,
        help="NORAD catalog number",
    )

    return parser.parse_args()


@observe_ingestion("celestrak")
def main() -> None:
    args = parse_args()

    records, from_cache = fetch_gp_by_catnr(
        args.catnr,
        cache_dir=Path(
            "/tmp/orbitalai/celestrak"
        ),
    )

    session_factory = get_session_factory()

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

    print(f"Source: {source}")
    print(f"Records: {result.records}")
    print(f"Objects created: {result.objects_created}")
    print(f"Objects updated: {result.objects_updated}")
    print(f"Elements created: {result.elements_created}")
    print(f"Elements existing: {result.elements_existing}")


if __name__ == "__main__":
    main()

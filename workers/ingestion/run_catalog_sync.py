from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from backend.app.services.catalog_sync_orchestrator import (
    DEFAULT_SYNC_ORDER,
    CatalogSyncAlreadyRunning,
    CatalogSyncSource,
    run_catalog_sync,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run OrbitalAI catalog synchronization."
        )
    )

    parser.add_argument(
        "--source",
        choices=(
            "all",
            "satcat",
            "celestrak",
            "space-track",
        ),
        default="all",
    )

    parser.add_argument(
        "--celestrak-group",
        default="ACTIVE",
    )

    parser.add_argument(
        "--celestrak-max-records",
        type=int,
        default=40_000,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if (
        args.celestrak_max_records
        <= 0
    ):
        raise ValueError(
            "--celestrak-max-records "
            "must be greater than zero"
        )

    if args.source == "all":
        sources = (
            DEFAULT_SYNC_ORDER
        )
    else:
        sources = (
            args.source,
        )

    try:
        outcomes = (
            run_catalog_sync(
                sources=(
                    sources
                ),
                celestrak_group=(
                    args.celestrak_group
                ),
                celestrak_max_records=(
                    args.celestrak_max_records
                ),
            )
        )

    except CatalogSyncAlreadyRunning as exc:
        print(
            str(exc),
            file=sys.stderr,
        )

        raise SystemExit(
            2
        ) from exc

    payload = [
        asdict(
            outcome
        )
        for outcome in outcomes
    ]

    print(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
    )

    if any(
        outcome.status
        != "success"
        for outcome in outcomes
    ):
        raise SystemExit(
            1
        )


if __name__ == "__main__":
    main()

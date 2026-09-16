from __future__ import annotations

from backend.app.observability.operations import observe_ingestion

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    timezone,
)
from typing import (
    Any,
    Iterable,
)

from sqlalchemy.orm import Session

from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.repositories.orbital_objects import (
    OrbitalObjectRepository,
)
from backend.app.services.orbital_object_types import (
    normalize_object_type,
)



@dataclass(
    frozen=True,
    slots=True,
)
class SatcatSyncResult:
    records: int

    created: int
    updated: int

    payloads: int
    rocket_bodies: int
    debris: int
    unknown: int
    other: int

    on_orbit: int
    decayed: int


def _optional_string(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    if not normalized:
        return None

    return normalized


def _optional_float(
    value: Any,
) -> float | None:
    normalized = _optional_string(
        value
    )

    if normalized is None:
        return None

    try:
        return float(
            normalized
        )
    except ValueError:
        return None


def _optional_date(
    value: Any,
) -> date | None:
    normalized = _optional_string(
        value
    )

    if normalized is None:
        return None

    try:
        return date.fromisoformat(
            normalized[:10]
        )
    except ValueError:
        return None


def build_satcat_object_values(
    record: dict[str, Any],
) -> tuple[
    int,
    dict[str, Any],
]:
    raw_cat_id = (
        record.get(
            "NORAD_CAT_ID"
        )
    )

    if raw_cat_id in (
        None,
        "",
    ):
        raise ValueError(
            "SATCAT record is missing NORAD_CAT_ID"
        )

    norad_cat_id = int(
        raw_cat_id
    )

    decay_date = (
        _optional_date(
            record.get(
                "DECAY_DATE"
            )
        )
    )

    orbit_center = (
        _optional_string(
            record.get(
                "ORBIT_CENTER"
            )
        )
    )

    orbit_type = (
        _optional_string(
            record.get(
                "ORBIT_TYPE"
            )
        )
    )

    values = {
        "object_name":
            _optional_string(
                record.get(
                    "OBJECT_NAME"
                )
            )
            or f"NORAD {norad_cat_id}",

        "object_id":
            _optional_string(
                record.get(
                    "OBJECT_ID"
                )
            ),

        "object_type":
            normalize_object_type(
                record.get(
                    "OBJECT_TYPE"
                )
            ),

        "ops_status_code":
            _optional_string(
                record.get(
                    "OPS_STATUS_CODE"
                )
            ),

        "owner":
            _optional_string(
                record.get(
                    "OWNER"
                )
            ),

        "launch_date":
            _optional_date(
                record.get(
                    "LAUNCH_DATE"
                )
            ),

        "launch_site":
            _optional_string(
                record.get(
                    "LAUNCH_SITE"
                )
            ),

        "decay_date":
            decay_date,

        "period_minutes":
            _optional_float(
                record.get(
                    "PERIOD"
                )
            ),

        "inclination_deg":
            _optional_float(
                record.get(
                    "INCLINATION"
                )
            ),

        "apogee_km":
            _optional_float(
                record.get(
                    "APOGEE"
                )
            ),

        "perigee_km":
            _optional_float(
                record.get(
                    "PERIGEE"
                )
            ),

        "rcs_m2":
            _optional_float(
                record.get(
                    "RCS"
                )
            ),

        "data_status_code":
            _optional_string(
                record.get(
                    "DATA_STATUS_CODE"
                )
            ),

        "orbit_center":
            orbit_center,

        "orbit_type":
            orbit_type,

        "is_on_orbit":
            decay_date is None,

        "is_earth_orbit":
            (
                decay_date is None
                and orbit_center == "EA"
                and orbit_type == "ORB"
            ),

        "source":
            "celestrak",

        "catalog_updated_at":
            datetime.now(
                timezone.utc
            ),
    }

    return (
        norad_cat_id,
        values,
    )


def _chunks(
    values: list[int],
    size: int = 5000,
):
    for offset in range(
        0,
        len(values),
        size,
    ):
        yield values[
            offset:
            offset + size
        ]


@observe_ingestion("satcat")
def sync_satcat_records(
    session: Session,
    records: Iterable[
        dict[str, Any]
    ],
) -> SatcatSyncResult:
    prepared: dict[
        int,
        dict[str, Any],
    ] = {}

    for record in records:
        (
            norad_cat_id,
            values,
        ) = (
            build_satcat_object_values(
                record
            )
        )

        prepared[
            norad_cat_id
        ] = values


    repository = (
        OrbitalObjectRepository(
            session
        )
    )


    existing: dict[
        int,
        OrbitalObject,
    ] = {}


    identifiers = list(
        prepared
    )


    for chunk in _chunks(
        identifiers
    ):
        for orbital_object in (
            repository
            .list_by_norad_cat_ids(
                chunk
            )
        ):
            existing[
                orbital_object
                .norad_cat_id
            ] = orbital_object


    created = 0
    updated = 0

    counts = {
        "PAYLOAD": 0,
        "ROCKET_BODY": 0,
        "DEBRIS": 0,
        "UNKNOWN": 0,
        "OTHER": 0,
    }

    on_orbit = 0
    decayed = 0


    try:
        for index, (
            norad_cat_id,
            values,
        ) in enumerate(
            prepared.items(),
            start=1,
        ):
            object_type = (
                values[
                    "object_type"
                ]
            )

            if object_type in counts:
                counts[
                    object_type
                ] += 1
            else:
                counts[
                    "OTHER"
                ] += 1


            if values[
                "is_on_orbit"
            ]:
                on_orbit += 1
            else:
                decayed += 1


            orbital_object = (
                existing.get(
                    norad_cat_id
                )
            )


            if orbital_object is None:
                orbital_object = (
                    OrbitalObject(
                        norad_cat_id=
                            norad_cat_id,
                        **values,
                    )
                )

                session.add(
                    orbital_object
                )

                existing[
                    norad_cat_id
                ] = orbital_object

                created += 1

            else:
                for field, value in (
                    values.items()
                ):
                    setattr(
                        orbital_object,
                        field,
                        value,
                    )

                updated += 1


            if (
                index % 5000
                == 0
            ):
                session.flush()


        session.commit()

    except Exception:
        session.rollback()
        raise


    return SatcatSyncResult(
        records=len(
            prepared
        ),

        created=created,
        updated=updated,

        payloads=counts[
            "PAYLOAD"
        ],

        rocket_bodies=counts[
            "ROCKET_BODY"
        ],

        debris=counts[
            "DEBRIS"
        ],

        unknown=counts[
            "UNKNOWN"
        ],

        other=counts[
            "OTHER"
        ],

        on_orbit=on_orbit,
        decayed=decayed,
    )

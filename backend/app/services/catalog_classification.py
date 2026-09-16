from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import (
    select,
    text,
)
from sqlalchemy.orm import Session

from backend.app.db.models.orbital_object import (
    OrbitalObject,
)
from backend.app.db.repositories.orbital_object_tags import (
    OrbitalObjectTagRepository,
)
from backend.app.db.repositories.orbital_objects import (
    OrbitalObjectRepository,
)


Tag = tuple[
    str,
    str,
]


@dataclass(
    frozen=True,
    slots=True,
)
class GroupClassification:
    group: str
    tags: tuple[
        Tag,
        ...,
    ]


GROUP_CLASSIFICATIONS = (
    GroupClassification(
        "STATIONS",
        (
            ("special", "space_station"),
        ),
    ),

    GroupClassification(
        "WEATHER",
        (
            ("mission", "weather"),
        ),
    ),

    GroupClassification(
        "RESOURCE",
        (
            ("mission", "earth_observation"),
        ),
    ),

    GroupClassification(
        "SARSAT",
        (
            ("mission", "search_and_rescue"),
        ),
    ),

    GroupClassification(
        "DMC",
        (
            ("mission", "disaster_monitoring"),
            ("mission", "earth_observation"),
        ),
    ),

    GroupClassification(
        "TDRSS",
        (
            ("mission", "data_relay"),
            ("mission", "communications"),
        ),
    ),

    GroupClassification(
        "ARGOS",
        (
            ("mission", "data_collection"),
        ),
    ),

    GroupClassification(
        "PLANET",
        (
            ("mission", "earth_observation"),
            ("constellation", "planet"),
        ),
    ),

    GroupClassification(
        "INTELSAT",
        (
            ("mission", "communications"),
            ("operator", "intelsat"),
        ),
    ),

    GroupClassification(
        "SES",
        (
            ("mission", "communications"),
            ("operator", "ses"),
        ),
    ),

    GroupClassification(
        "EUTELSAT",
        (
            ("mission", "communications"),
            ("operator", "eutelsat"),
        ),
    ),

    GroupClassification(
        "TELESAT",
        (
            ("mission", "communications"),
            ("operator", "telesat"),
        ),
    ),

    GroupClassification(
        "STARLINK",
        (
            ("mission", "communications"),
            ("constellation", "starlink"),
        ),
    ),

    GroupClassification(
        "ONEWEB",
        (
            ("mission", "communications"),
            ("constellation", "oneweb"),
        ),
    ),

    GroupClassification(
        "QIANFAN",
        (
            ("mission", "communications"),
            ("constellation", "qianfan"),
        ),
    ),

    GroupClassification(
        "HULIANWANG",
        (
            ("mission", "communications"),
            ("constellation", "hulianwang"),
        ),
    ),

    GroupClassification(
        "KUIPER",
        (
            ("mission", "communications"),
            ("constellation", "kuiper"),
        ),
    ),

    GroupClassification(
        "IRIDIUM-NEXT",
        (
            ("mission", "communications"),
            ("constellation", "iridium_next"),
        ),
    ),

    GroupClassification(
        "ORBCOMM",
        (
            ("mission", "communications"),
            ("constellation", "orbcomm"),
        ),
    ),

    GroupClassification(
        "GLOBALSTAR",
        (
            ("mission", "communications"),
            ("constellation", "globalstar"),
        ),
    ),

    GroupClassification(
        "AMATEUR",
        (
            ("mission", "amateur_radio"),
        ),
    ),

    GroupClassification(
        "GNSS",
        (
            ("mission", "navigation"),
        ),
    ),

    GroupClassification(
        "GPS-OPS",
        (
            ("mission", "navigation"),
            ("constellation", "gps"),
        ),
    ),

    GroupClassification(
        "GLO-OPS",
        (
            ("mission", "navigation"),
            ("constellation", "glonass"),
        ),
    ),

    GroupClassification(
        "GALILEO",
        (
            ("mission", "navigation"),
            ("constellation", "galileo"),
        ),
    ),

    GroupClassification(
        "BEIDOU",
        (
            ("mission", "navigation"),
            ("constellation", "beidou"),
        ),
    ),

    GroupClassification(
        "SBAS",
        (
            ("mission", "navigation"),
            ("mission", "augmentation"),
        ),
    ),

    GroupClassification(
        "SCIENCE",
        (
            ("mission", "scientific"),
        ),
    ),

    GroupClassification(
        "GEODETIC",
        (
            ("mission", "scientific"),
            ("mission", "geodetic"),
        ),
    ),

    GroupClassification(
        "EDUCATION",
        (
            ("mission", "education"),
        ),
    ),

    GroupClassification(
        "MILITARY",
        (
            ("mission", "military"),
        ),
    ),

    GroupClassification(
        "RADAR",
        (
            ("special", "radar_calibration"),
        ),
    ),

    GroupClassification(
        "CUBESAT",
        (
            ("form_factor", "cubesat"),
        ),
    ),
)


def seed_object_type_tags(
    session: Session,
) -> int:
    statement = text(
        """
        INSERT INTO orbital_object_tags (
            orbital_object_id,
            namespace,
            tag,
            source
        )
        SELECT
            id,
            'object_type',
            lower(object_type),
            'satcat'
        FROM orbital_objects
        WHERE object_type IS NOT NULL
        ON CONFLICT
            ON CONSTRAINT uq_orbital_object_tag
        DO NOTHING
        """
    )

    result = session.execute(
        statement
    )

    session.commit()

    return (
        result.rowcount
        if result.rowcount
        is not None
        else 0
    )


def apply_group_tags(
    session: Session,
    *,
    group: str,
    records: list[
        dict[str, object]
    ],
    tags: tuple[
        Tag,
        ...,
    ],
) -> tuple[
    int,
    int,
]:
    norad_ids = sorted({
        int(
            record[
                "NORAD_CAT_ID"
            ]
        )
        for record in records
        if record.get(
            "NORAD_CAT_ID"
        )
    })


    object_repository = (
        OrbitalObjectRepository(
            session
        )
    )


    objects = (
        object_repository
        .list_by_norad_cat_ids(
            norad_ids
        )
    )


    rows: list[
        dict[str, object]
    ] = []


    effective_tags = (
        tags
        + (
            (
                "celestrak_group",
                group.lower(),
            ),
        )
    )


    for orbital_object in objects:
        for namespace, tag in (
            effective_tags
        ):
            rows.append({
                "orbital_object_id":
                    orbital_object.id,

                "namespace":
                    namespace,

                "tag":
                    tag,

                "source":
                    "celestrak_group",
            })


    repository = (
        OrbitalObjectTagRepository(
            session
        )
    )


    inserted = (
        repository.add_many(
            rows
        )
    )


    session.commit()


    return (
        len(objects),
        inserted,
    )


def count_tagged_objects(
    session: Session,
) -> int:
    statement = text(
        """
        SELECT COUNT(
            DISTINCT orbital_object_id
        )
        FROM orbital_object_tags
        """
    )

    return int(
        session.scalar(
            statement
        )
        or 0
    )


def count_current_elements(
    session: Session,
) -> int:
    statement = (
        select(
            OrbitalObject.id
        )
        .where(
            OrbitalObject
            .has_current_elements
            .is_(True)
        )
    )

    return len(
        session.scalars(
            statement
        ).all()
    )

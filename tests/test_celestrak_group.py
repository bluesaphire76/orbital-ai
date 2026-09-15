import pytest

from ingestion.celestrak import (
    normalize_group_name,
)


@pytest.mark.parametrize(
    (
        "value",
        "expected",
    ),
    [
        ("stations", "STATIONS"),
        ("GPS-OPS", "GPS-OPS"),
        (" active ", "ACTIVE"),
    ],
)
def test_normalize_group_name(
    value: str,
    expected: str,
) -> None:
    assert (
        normalize_group_name(value)
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "../../etc/passwd",
        "STATIONS?FORMAT=CSV",
        "GROUP=ACTIVE",
    ],
)
def test_invalid_group_name_is_rejected(
    value: str,
) -> None:
    with pytest.raises(
        ValueError
    ):
        normalize_group_name(value)

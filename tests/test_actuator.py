"""Angle <-> position mapping and travel estimates."""

from __future__ import annotations

import pytest

from custom_components.helios_tilt.actuator import (
    AngleMapping,
    MappingError,
    estimate_angle,
    parse_table,
    travel_seconds,
)


def test_linear_and_inverted() -> None:
    """Both ways, clamped, invertible."""
    m = AngleMapping.linear(0, 60, 0, 100)
    assert m.to_position(30) == pytest.approx(50)
    assert m.to_angle(50) == pytest.approx(30)
    assert m.to_position(90) == 100
    inv = AngleMapping.linear(0, 60, 100, 0)
    assert inv.to_position(15) == pytest.approx(75)
    assert inv.to_angle(75) == pytest.approx(15)
    assert inv.position_range == (0, 100)


def test_linear_errors() -> None:
    """Bad end points."""
    with pytest.raises(MappingError):
        AngleMapping.linear(10, 10, 0, 100)
    with pytest.raises(MappingError):
        AngleMapping.linear(0, 60, 50, 50)


def test_table() -> None:
    """Piecewise linear through the calibration points."""
    m = AngleMapping.table("0:0, 15:22; 30:47\n45:75, 60:100")
    assert m.to_position(15) == pytest.approx(22)
    assert m.to_position(22.5) == pytest.approx(34.5)
    assert m.to_angle(34.5) == pytest.approx(22.5)
    falling = AngleMapping.table("60:0, 0:200")
    assert falling.to_angle(100) == pytest.approx(30)


@pytest.mark.parametrize(
    "text",
    ["", "0:0", "0:0, 10", "0:0, a:1", "0:0, 0:5", "0:0, 10:50, 20:40"],
)
def test_table_errors(text: str) -> None:
    """Unusable tables are rejected."""
    with pytest.raises(MappingError):
        parse_table(text)


def test_travel_estimate() -> None:
    """Open loop: proportional to the distance."""
    assert travel_seconds(0, 30, 60, 60) == 30
    assert travel_seconds(0, 30, 0, 60) == 0
    assert estimate_angle(0, 30, 15, 30) == 15
    assert estimate_angle(0, 30, 45, 30) == 30
    assert estimate_angle(10, 0, 0, 10) == 10
    assert estimate_angle(0, 30, 5, 0) == 30

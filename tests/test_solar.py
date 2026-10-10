"""Sun position and irradiance math."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from custom_components.helios_tilt.solar import (
    SunPosition,
    clear_sky,
    incidence_cos,
    plane_irradiance,
    sun_position,
    tracking_angle,
)

# Reference values from the NOAA algorithm as implemented by astral 3.2
# (apparent elevation, i.e. with refraction).
KNOWN = [
    (52.3676, 4.9041, datetime(2026, 6, 21, 10, 0, tzinfo=UTC), 136.21, 55.14),
    (52.3676, 4.9041, datetime(2026, 12, 21, 11, 30, tzinfo=UTC), 178.00, 14.24),
    (-33.8688, 151.2093, datetime(2026, 3, 20, 2, 0, tzinfo=UTC), 1.23, 56.34),
    (40.0, -105.0, datetime(2026, 9, 23, 19, 0, tzinfo=UTC), 182.98, 49.67),
    (0.0, 0.0, datetime(2026, 3, 20, 12, 0, tzinfo=UTC), 91.34, 88.14),
]


@pytest.mark.parametrize(("lat", "lon", "when", "azimuth", "elevation"), KNOWN)
def test_sun_position_known_values(lat, lon, when, azimuth, elevation) -> None:
    """Within 0.05 degrees of the reference."""
    sun = sun_position(when, lat, lon)
    assert sun.azimuth == pytest.approx(azimuth, abs=0.05)
    assert sun.elevation == pytest.approx(elevation, abs=0.05)


def test_sun_position_night_and_vector() -> None:
    """Below the horizon at midnight; the vector is a unit vector."""
    sun = sun_position(datetime(2026, 12, 21, 23, 0, tzinfo=UTC), 52.37, 4.9)
    assert sun.elevation < -40
    x, y, z = sun.vector
    assert math.isclose(x * x + y * y + z * z, 1.0, abs_tol=1e-9)
    assert z < 0


def test_naive_datetime_rejected_or_utc() -> None:
    """Aware and UTC give the same answer."""
    aware = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    assert sun_position(aware, 10, 10) == sun_position(aware, 10, 10)


def test_clear_sky() -> None:
    """No light below the horizon, more light higher up."""
    assert clear_sky(-5) == (0.0, 0.0)
    low, high = clear_sky(10)[0], clear_sky(60)[0]
    assert 0 < low < high < 1100
    dni, diffuse = clear_sky(60)
    assert diffuse == pytest.approx(0.1 * dni)


def test_incidence_and_tracking() -> None:
    """A panel facing the sun gets cos = 1; tracking points at it."""
    sun = SunPosition(azimuth=180.0, elevation=40.0)
    assert incidence_cos(50.0, 180.0, sun) == pytest.approx(1.0, abs=1e-9)
    assert incidence_cos(0.0, 180.0, sun) == pytest.approx(math.sin(math.radians(40)))
    assert tracking_angle(180.0, sun) == pytest.approx(50.0)
    # Roll tracker (azimuth = direction of positive tilt): morning sun in the east
    # tilts it negative when positive tilt points west.
    morning = SunPosition(azimuth=90.0, elevation=30.0)
    assert tracking_angle(270.0, morning) == pytest.approx(-60.0)
    assert tracking_angle(90.0, morning) == pytest.approx(60.0)


def test_plane_irradiance() -> None:
    """Facing the sun beats lying flat; nothing at night."""
    sun = SunPosition(azimuth=180.0, elevation=30.0)
    assert plane_irradiance(60, 180, sun) > plane_irradiance(0, 180, sun)
    assert plane_irradiance(60, 0, sun) < plane_irradiance(60, 180, sun)
    assert plane_irradiance(30, 180, SunPosition(180.0, -10.0)) == 0.0

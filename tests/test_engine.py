"""Angle strategies."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest

from custom_components.helios_tilt.engine import (
    PanelGeometry,
    annual_optimum,
    daily_optimum,
    is_night,
    round_to_step,
    seasonal_angle,
    tracking_target,
)
from custom_components.helios_tilt.solar import SunPosition

AMS = ZoneInfo("Europe/Amsterdam")
GEO = PanelGeometry(52.3676, 4.9041, 180.0, 0.0, 90.0)


def test_annual_optimum_amsterdam() -> None:
    """Clear-sky annual optimum is steeper than latitude minus a bit, below latitude."""
    angle = annual_optimum(GEO, 2026, AMS)
    assert 34 <= angle <= 45


def test_annual_optimum_respects_limits() -> None:
    """Never outside the soft limits."""
    geo = PanelGeometry(52.37, 4.9, 180.0, 0.0, 25.0)
    assert annual_optimum(geo, 2026, AMS) == 25.0


def test_daily_optimum_follows_season() -> None:
    """Flat in summer, steep in winter, equinox near latitude."""
    summer = daily_optimum(GEO, date(2026, 6, 21), AMS)
    winter = daily_optimum(GEO, date(2026, 12, 21), AMS)
    equinox = daily_optimum(GEO, date(2026, 3, 20), AMS)
    assert summer < equinox < winter
    assert summer <= 20
    assert winter >= 65
    assert 40 <= equinox <= 60


def test_daily_optimum_southern_hemisphere() -> None:
    """Sydney panels face north; June is winter there."""
    geo = PanelGeometry(-33.87, 151.21, 0.0, 0.0, 90.0)
    tz = ZoneInfo("Australia/Sydney")
    assert daily_optimum(geo, date(2026, 6, 21), tz) > daily_optimum(
        geo, date(2026, 12, 21), tz
    )


def test_seasonal_angle() -> None:
    """Winter angle at the winter solstice, summer angle at the summer solstice."""
    assert seasonal_angle(date(2026, 12, 21), 52, 60, 20, 50) == pytest.approx(
        60, abs=0.1
    )
    assert seasonal_angle(date(2026, 6, 21), 52, 60, 20, 50) == pytest.approx(
        20, abs=0.2
    )
    mid = seasonal_angle(date(2026, 3, 21), 52, 60, 20, 50)
    assert 35 < mid < 45
    # Weight leans the curve.
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 80) > mid
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 20) < mid
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 100) == pytest.approx(60)
    assert seasonal_angle(date(2026, 3, 21), 52, 60, 20, 0) == pytest.approx(20)
    # Southern hemisphere: June is winter.
    assert seasonal_angle(date(2026, 6, 21), -33, 60, 20, 50) == pytest.approx(
        60, abs=0.2
    )


def test_tracking_target_clamped() -> None:
    """Tracking points at the sun within the limits."""
    geo = PanelGeometry(52, 5, 180.0, 0.0, 60.0)
    assert tracking_target(geo, SunPosition(180.0, 40.0)) == pytest.approx(50.0)
    assert tracking_target(geo, SunPosition(180.0, 10.0)) == 60.0
    roll = PanelGeometry(52, 5, 270.0, -45.0, 45.0)
    assert tracking_target(roll, SunPosition(90.0, 20.0)) == -45.0
    assert tracking_target(roll, SunPosition(180.0, 60.0)) == pytest.approx(
        0.0, abs=1e-6
    )


def test_round_to_step_with_hysteresis() -> None:
    """Rounds to the step; sticks to the current step near a boundary."""
    assert round_to_step(13.0, 5, None, 1) == 15
    assert round_to_step(12.4, 5, None, 1) == 10
    # Current 10: 13.4 is within 2.5 + 1 -> stay.
    assert round_to_step(13.4, 5, 10, 1) == 10
    assert round_to_step(13.6, 5, 10, 1) == 15
    # Falling back just under the boundary does not flip back.
    assert round_to_step(12.0, 5, 15, 1) == 15
    assert round_to_step(11.4, 5, 15, 1) == 10
    assert round_to_step(13.3, 0, 10, 1) == 13.3
    assert round_to_step(-12.6, 5, None, 0) == -15


def test_is_night() -> None:
    """Night below -1 degree."""
    assert is_night(SunPosition(0, -5))
    assert not is_night(SunPosition(0, 0))

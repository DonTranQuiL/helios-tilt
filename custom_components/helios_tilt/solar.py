"""Sun position and clear-sky irradiance. Pure Python, no Home Assistant imports.

Sun position follows the NOAA solar calculator equations (accurate to about
0.01 degree between 1800 and 2100), including atmospheric refraction.
Irradiance uses the Meinel clear-sky model with the Kasten-Young air mass.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

_RAD = math.pi / 180.0


@dataclass(frozen=True, slots=True)
class SunPosition:
    """Sun direction seen from the site (degrees)."""

    azimuth: float  # clockwise from north
    elevation: float  # above the horizon, refraction included

    @property
    def vector(self) -> tuple[float, float, float]:
        """Unit vector to the sun in (east, north, up)."""
        ce = math.cos(self.elevation * _RAD)
        return (
            ce * math.sin(self.azimuth * _RAD),
            ce * math.cos(self.azimuth * _RAD),
            math.sin(self.elevation * _RAD),
        )


def _julian_day(when: datetime) -> float:
    when = when.astimezone(UTC)
    return when.timestamp() / 86400.0 + 2440587.5


def _refraction(elevation: float) -> float:
    """NOAA approximation of atmospheric refraction (degrees)."""
    if elevation > 85.0:
        return 0.0
    te = math.tan(elevation * _RAD)
    if elevation > 5.0:
        arcsec = 58.1 / te - 0.07 / te**3 + 0.000086 / te**5
    elif elevation > -0.575:
        arcsec = 1735.0 + elevation * (
            -518.2 + elevation * (103.4 + elevation * (-12.79 + elevation * 0.711))
        )
    else:
        arcsec = -20.772 / te
    return arcsec / 3600.0


def sun_position(when: datetime, latitude: float, longitude: float) -> SunPosition:
    """Return the sun's azimuth and elevation at `when` (timezone aware)."""
    jc = (_julian_day(when) - 2451545.0) / 36525.0
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360.0
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    c = (
        math.sin(m * _RAD) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
        + math.sin(2 * m * _RAD) * (0.019993 - 0.000101 * jc)
        + math.sin(3 * m * _RAD) * 0.000289
    )
    omega = 125.04 - 1934.136 * jc
    app_long = l0 + c - 0.00569 - 0.00478 * math.sin(omega * _RAD)
    obliq = (
        23.0
        + (26.0 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60.0)
        / 60.0
        + 0.00256 * math.cos(omega * _RAD)
    )
    decl = math.asin(math.sin(obliq * _RAD) * math.sin(app_long * _RAD))
    y = math.tan(obliq * _RAD / 2.0) ** 2
    eq_time = (
        4.0
        / _RAD
        * (
            y * math.sin(2 * l0 * _RAD)
            - 2 * e * math.sin(m * _RAD)
            + 4 * e * y * math.sin(m * _RAD) * math.cos(2 * l0 * _RAD)
            - 0.5 * y * y * math.sin(4 * l0 * _RAD)
            - 1.25 * e * e * math.sin(2 * m * _RAD)
        )
    )
    utc = when.astimezone(UTC)
    minutes = utc.hour * 60 + utc.minute + utc.second / 60 + utc.microsecond / 6e7
    true_solar = (minutes + eq_time + 4.0 * longitude) % 1440.0
    hour_angle = true_solar / 4.0 - 180.0

    lat = latitude * _RAD
    cos_zen = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(
        decl
    ) * math.cos(hour_angle * _RAD)
    zenith = math.acos(max(-1.0, min(1.0, cos_zen)))
    sin_zen = math.sin(zenith)
    if abs(math.cos(lat) * sin_zen) < 1e-9:
        azimuth = 180.0 if latitude > 0 else 0.0
    else:
        cos_az = (math.sin(lat) * math.cos(zenith) - math.sin(decl)) / (
            math.cos(lat) * sin_zen
        )
        az = math.acos(max(-1.0, min(1.0, cos_az))) / _RAD
        azimuth = (az + 180.0) % 360.0 if hour_angle > 0 else (540.0 - az) % 360.0
    elevation = 90.0 - zenith / _RAD
    return SunPosition(azimuth, elevation + _refraction(elevation))


def clear_sky(elevation: float) -> tuple[float, float]:
    """Return (direct normal, diffuse horizontal) clear-sky irradiance in W/m2."""
    if elevation <= 0.0:
        return 0.0, 0.0
    zenith = 90.0 - elevation
    air_mass = 1.0 / (
        math.cos(zenith * _RAD) + 0.50572 * (96.07995 - zenith) ** -1.6364
    )
    dni = 1353.0 * 0.7 ** (air_mass**0.678)
    return dni, 0.1 * dni


def tilt_direction(azimuth: float) -> tuple[float, float, float]:
    """Horizontal unit vector the panel tilts toward (east, north, up)."""
    return (math.sin(azimuth * _RAD), math.cos(azimuth * _RAD), 0.0)


def incidence_cos(angle: float, azimuth: float, sun: SunPosition) -> float:
    """Cosine of the angle between the panel normal and the sun.

    The panel normal is the zenith tilted by `angle` toward `azimuth`. That
    covers a fixed-tilt rack (azimuth = direction it faces) and a single-axis
    tracker (azimuth = 90 degrees right of the axis direction, angle may be
    negative).
    """
    sx, sy, sz = sun.vector
    hx, hy, _ = tilt_direction(azimuth)
    sin_a = math.sin(angle * _RAD)
    return math.cos(angle * _RAD) * sz + sin_a * (sx * hx + sy * hy)


def plane_irradiance(angle: float, azimuth: float, sun: SunPosition) -> float:
    """Clear-sky irradiance on the panel (W/m2): beam plus isotropic diffuse."""
    dni, dhi = clear_sky(sun.elevation)
    if dni <= 0.0:
        return 0.0
    beam = dni * max(0.0, incidence_cos(angle, azimuth, sun))
    diffuse = dhi * (1.0 + math.cos(angle * _RAD)) / 2.0
    return beam + diffuse


def tracking_angle(azimuth: float, sun: SunPosition) -> float:
    """Angle that points the panel's normal closest to the sun.

    This is the sun elevation projected onto the panel's tilt plane:
    atan2(sun component along the tilt direction, sun component up).
    """
    sx, sy, sz = sun.vector
    hx, hy, _ = tilt_direction(azimuth)
    return math.atan2(sx * hx + sy * hy, sz) / _RAD


def best_angle(azimuth: float, sun: SunPosition) -> float:
    """Angle with the most clear-sky irradiance on the panel (beam + diffuse).

    Pointing straight at the sun maximises the beam, but tilting also loses
    some sky diffuse, so the best angle is a little flatter than
    `tracking_angle`. Setting the derivative of `plane_irradiance` to zero
    gives atan2(dni * p, dni * z + dhi / 2), with p and z the sun components
    along the tilt direction and up. The irradiance is unimodal in the angle,
    so clamping this to the limits gives the best angle within them.
    """
    dni, dhi = clear_sky(sun.elevation)
    if dni <= 0.0:
        return tracking_angle(azimuth, sun)
    sx, sy, sz = sun.vector
    hx, hy, _ = tilt_direction(azimuth)
    return math.atan2(dni * (sx * hx + sy * hy), dni * sz + dhi / 2.0) / _RAD

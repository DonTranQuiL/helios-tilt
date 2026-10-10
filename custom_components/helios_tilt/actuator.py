"""Angle <-> actuator position mapping (pure, no Home Assistant imports)."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass


class MappingError(ValueError):
    """The calibration table can't be used."""


def parse_table(text: str) -> list[tuple[float, float]]:
    """Parse 'angle:position' pairs separated by commas, semicolons or lines.

    Example: "0:0, 15:22, 30:47, 45:75, 60:100". Angles must be unique and
    positions must rise or fall consistently (the mapping must be invertible).
    """
    pairs: list[tuple[float, float]] = []
    for chunk in text.replace(";", ",").replace("\n", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise MappingError(f"'{chunk}' is not angle:position")
        angle, position = chunk.split(":", 1)
        try:
            pairs.append((float(angle), float(position)))
        except ValueError as err:
            raise MappingError(f"'{chunk}' is not a number pair") from err
    if len(pairs) < 2:
        raise MappingError("needs at least two angle:position pairs")
    pairs.sort()
    angles = [a for a, _ in pairs]
    if len(set(angles)) != len(angles):
        raise MappingError("an angle appears twice")
    steps = [b[1] - a[1] for a, b in zip(pairs, pairs[1:], strict=False)]
    if not (all(d > 0 for d in steps) or all(d < 0 for d in steps)):
        raise MappingError("positions must rise (or fall) with the angle")
    return pairs


def _interpolate(points: list[tuple[float, float]], x: float) -> float:
    """Piecewise-linear interpolation with clamping; points sorted by x."""
    xs = [p[0] for p in points]
    if x <= xs[0]:
        return points[0][1]
    if x >= xs[-1]:
        return points[-1][1]
    i = bisect_left(xs, x)
    (x0, y0), (x1, y1) = points[i - 1], points[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


@dataclass(slots=True)
class AngleMapping:
    """Convert between panel angle and actuator position, both directions."""

    points: list[tuple[float, float]]  # (angle, position), sorted by angle

    @classmethod
    def linear(
        cls, min_angle: float, max_angle: float, pos_at_min: float, pos_at_max: float
    ) -> AngleMapping:
        """Straight line between the two end points (swap them to invert)."""
        if max_angle <= min_angle:
            raise MappingError("max angle must be above min angle")
        if pos_at_min == pos_at_max:
            raise MappingError("the two end positions must differ")
        return cls([(min_angle, pos_at_min), (max_angle, pos_at_max)])

    @classmethod
    def table(cls, text: str) -> AngleMapping:
        """From a calibration table."""
        return cls(parse_table(text))

    def to_position(self, angle: float) -> float:
        """Actuator position for an angle."""
        return _interpolate(self.points, angle)

    def to_angle(self, position: float) -> float:
        """Angle for an actuator position (inverse)."""
        inverse = sorted((p, a) for a, p in self.points)
        return _interpolate(inverse, position)

    @property
    def position_range(self) -> tuple[float, float]:
        """Lowest and highest position used."""
        positions = [p for _, p in self.points]
        return min(positions), max(positions)


def travel_seconds(
    from_angle: float, to_angle: float, full_range: float, full_stroke: float
) -> float:
    """Open-loop travel time estimate for a move."""
    if full_range <= 0:
        return 0.0
    return abs(to_angle - from_angle) / full_range * full_stroke


def estimate_angle(
    start: float, target: float, elapsed: float, duration: float
) -> float:
    """Where an open-loop actuator should be `elapsed` seconds into a move."""
    if duration <= 0 or elapsed >= duration:
        return target
    return start + (target - start) * max(0.0, elapsed) / duration

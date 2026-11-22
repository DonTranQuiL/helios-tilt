"""Frost guard: park once before the freeze, then refuse moves until it thaws.

Pure state machine (no Home Assistant imports). The controller feeds it a
temperature (or None when the sensor is missing, unknown, unavailable or
stale) on every tick. A restart restores the persisted fields so a frozen
panel is never commanded again until the unlock hold has passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(slots=True)
class FrostGuardSettings:
    """Site options for the frost guard (off by default)."""

    enabled: bool = False
    park_temperature: float = 1.0
    unlock_temperature: float = 2.0
    unlock_hold: timedelta = timedelta(minutes=45)
    allow_storm: bool = True


@dataclass(slots=True)
class FrostGuardStatus:
    """Outcome of one evaluation."""

    locked: bool = False
    should_park: bool = False  # just locked: issue the one park move
    locked_since: datetime | None = None
    above_since: datetime | None = None
    unlock_eta: datetime | None = None


@dataclass(slots=True)
class FrostGuard:
    """Remembers the lock, the park, and the thaw timer between ticks."""

    settings: FrostGuardSettings
    locked: bool = False
    locked_since: datetime | None = None
    above_since: datetime | None = None
    park_issued: bool = False

    def evaluate(self, now: datetime, temperature: float | None) -> FrostGuardStatus:
        """Update the lock. `temperature` is None when the reading is unusable."""
        should_park = False
        if not self.settings.enabled:
            self.locked = False
            self.locked_since = None
            self.above_since = None
            self.park_issued = False
            return FrostGuardStatus()

        if self.locked:
            if temperature is None:
                # Missing or stale: stay locked and restart the thaw timer.
                self.above_since = None
            elif temperature > self.settings.unlock_temperature:
                if self.above_since is None:
                    self.above_since = now
                if now - self.above_since >= self.settings.unlock_hold:
                    self.locked = False
                    self.locked_since = None
                    self.above_since = None
                    self.park_issued = False
            else:
                self.above_since = None
        elif temperature is not None and temperature <= self.settings.park_temperature:
            self.locked = True
            self.locked_since = now
            self.above_since = None
            should_park = not self.park_issued
            # Persist as issued immediately so a crash or restart cannot
            # command a second move while the panel is already freezing.
            self.park_issued = True

        unlock_eta = None
        if self.locked and self.above_since is not None:
            unlock_eta = self.above_since + self.settings.unlock_hold
        return FrostGuardStatus(
            locked=self.locked,
            should_park=should_park,
            locked_since=self.locked_since,
            above_since=self.above_since,
            unlock_eta=unlock_eta,
        )

    def store_data(self) -> dict[str, Any]:
        """Fields that must survive a restart."""
        return {
            "locked": self.locked,
            "locked_since": self.locked_since.isoformat()
            if self.locked_since
            else None,
            "above_since": self.above_since.isoformat() if self.above_since else None,
            "park_issued": self.park_issued,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Load the lock from the Store. Invalid dates are skipped."""
        self.locked = bool(data.get("locked", False))
        self.park_issued = bool(data.get("park_issued", self.locked))
        self.locked_since = _parse(data.get("locked_since"))
        self.above_since = _parse(data.get("above_since"))
        if not self.locked:
            self.locked_since = None
            self.above_since = None
            self.park_issued = False


def _parse(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

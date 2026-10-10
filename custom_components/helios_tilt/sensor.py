"""Sensors: target and current angle, last move, moves today, gain, PV."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeliosConfigEntry
from .const import (
    REASON_CALIBRATE,
    REASON_DIFFUSE,
    REASON_FROST,
    REASON_MANUAL,
    REASON_NIGHT,
    REASON_RAIN,
    REASON_SNOW,
    REASON_STORM,
    REASON_STOW,
    REASON_STRATEGY,
    REASON_WIND,
)
from .controller import HeliosSite, Panel
from .entity import HeliosEntity

REASONS = [
    REASON_STRATEGY,
    REASON_NIGHT,
    REASON_DIFFUSE,
    REASON_MANUAL,
    REASON_WIND,
    REASON_STORM,
    REASON_STOW,
    REASON_SNOW,
    REASON_RAIN,
    REASON_FROST,
    REASON_CALIBRATE,
]


@dataclass(frozen=True, kw_only=True)
class HeliosSensorDescription(SensorEntityDescription):
    """Sensor with value and attribute functions."""

    value_fn: Callable[[HeliosSite, Panel], Any]
    attrs_fn: Callable[[HeliosSite, Panel], dict[str, Any]] | None = None
    available_fn: Callable[[Panel], bool] = lambda panel: True


def _target_attrs(site: HeliosSite, panel: Panel) -> dict[str, Any]:
    sun = site.sun
    return {
        "mode": panel.mode,
        "strategy": panel.strategy,
        "reason": panel.target_reason,
        "detail": panel.target_detail,
        "safety": site.safety.last.state,
        "safety_detail": site.safety.last.detail,
        "auto": panel.auto_enabled,
        "stowed": panel.stowed,
        "paused_until": panel.manual_until.isoformat() if panel.manual_until else None,
        "min_angle": panel.cfg.min_angle,
        "max_angle": panel.cfg.max_angle,
        "stow_angle": panel.cfg.stow_angle,
        "azimuth": panel.cfg.azimuth,
        "axis": panel.cfg.axis,
        "fixed_optimum": panel.fixed_angle,
        "sun_azimuth": None if sun is None else round(sun.azimuth, 1),
        "sun_elevation": None if sun is None else round(sun.elevation, 1),
        "today_curve": [list(p) for p in panel.today_curve],
        "sun_path": [list(p) for p in site.sun_path],
    }


def _current_attrs(panel: Panel) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "source": panel.current_source,
        "moving": panel.moving,
        "commanded": panel.commanded,
        "stuck": panel.stuck,
        "actuator_type": panel.cfg.actuator_type,
    }
    if (driver := panel.driver) is not None:
        position = driver.current_position()
        cal = driver.calibration
        attrs.update(
            {
                "estimated": True,
                "position_uncertain": driver.uncertain,
                "stroke": None if position is None else round(position, 1),
                "direction": {1: "opening", -1: "closing"}.get(driver.direction),
                "calibration": None
                if cal is None
                else {
                    k: cal.get(k)
                    for k in ("phase", "open_time", "close_time", "phase_started")
                },
            }
        )
    return attrs


def _last_move_attrs(site: HeliosSite, panel: Panel) -> dict[str, Any]:
    last = panel.last_move
    return {
        "angle": None if last is None else last.angle,
        "detail": None if last is None else last.detail,
        "time": None if last is None else last.time.isoformat(),
        "history": [m.as_dict() for m in reversed(panel.history)],
    }


SENSORS: tuple[HeliosSensorDescription, ...] = (
    HeliosSensorDescription(
        key="target_angle",
        translation_key="target_angle",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda site, panel: panel.target,
        attrs_fn=_target_attrs,
    ),
    HeliosSensorDescription(
        key="current_angle",
        translation_key="current_angle",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda site, panel: panel.current,
        attrs_fn=lambda site, panel: _current_attrs(panel),
    ),
    HeliosSensorDescription(
        key="last_move",
        translation_key="last_move",
        device_class=SensorDeviceClass.ENUM,
        options=REASONS,
        value_fn=lambda site, panel: (
            panel.last_move.reason if panel.last_move else None
        ),
        attrs_fn=_last_move_attrs,
    ),
    HeliosSensorDescription(
        key="moves_today",
        translation_key="moves_today",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda site, panel: panel.moves_today,
    ),
    HeliosSensorDescription(
        key="gain",
        translation_key="gain",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda site, panel: panel.gain,
        attrs_fn=lambda site, panel: {
            "basis": "today, clear-sky model, while following the strategy",
            "modelled_wh_m2": round(panel.energy_actual, 1),
            "fixed_wh_m2": round(panel.energy_fixed, 1),
            "fixed_angle": site.fixed_reference(panel),
            "instant_gain": panel.instant_gain,
            "counted_since": panel.energy_since.isoformat()
            if panel.energy_since
            else None,
            "excluded_minutes": round(panel.excluded_seconds / 60.0),
        },
    ),
)

PV_SENSOR = HeliosSensorDescription(
    key="pv_performance",
    translation_key="pv_performance",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
    value_fn=lambda site, panel: panel.pv_performance,
    attrs_fn=lambda site, panel: {
        "actual_power": panel.pv_actual,
        "model_power": panel.pv_model,
        "peak_power": panel.cfg.pv_peak_power,
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One set of sensors per panel."""
    site = entry.runtime_data
    for panel in site.panels.values():
        descriptions = list(SENSORS)
        if panel.cfg.pv_power_entity and panel.cfg.pv_peak_power:
            descriptions.append(PV_SENSOR)
        async_add_entities(
            [HeliosSensor(site, panel, d) for d in descriptions],
            config_subentry_id=panel.id,
        )


class HeliosSensor(HeliosEntity, SensorEntity):
    """A panel sensor."""

    entity_description: HeliosSensorDescription
    _unrecorded_attributes = frozenset(
        {
            "today_curve",
            "sun_path",
            "safety_detail",
            "paused_until",
            "history",
            "min_angle",
            "max_angle",
            "stow_angle",
            "azimuth",
            "axis",
            "basis",
            "instant_gain",
            "counted_since",
        }
    )

    @property
    def native_value(self) -> Any:
        """Current value."""
        return self.entity_description.value_fn(self.site, self.panel)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Extra data (also used by the card)."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.site, self.panel)

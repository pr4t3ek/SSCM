"""Total logistics cost as a function of Base Fleet Capacity (B).

Total(B) = Base Fleet Cost + Spot Cost + Expected Demurrage + Expected Shortage Cost

    Spot_t        = max(Required(t) - B, 0)                     # spot rakes sourced that day
    Idle_t        = max(B - Required(t), 0)                      # base-fleet rakes unused that day
    Shortfall_t   = max(Spot_t - spot_availability_cap, 0)        # spot demand IR couldn't fill
    UnmetTonnes_t = Shortfall_t * rake_capacity_t

Demurrage is charged on *idle base-fleet capacity*, mirroring the proposal's
own framing ("demurrage/overbooking charges during slumps") -- i.e. an
overcommitted captive/leased fleet sitting idle when demand is low, not a
generic siding-delay charge. This modeling choice is stated explicitly on the
Cost Model appendix page rather than presented as an unquestioned fact.

All rupee parameters below are ASSUMPTION-grade illustrative defaults (see
config.DEFAULT_PARAMS for provenance), never fabricated official CIL/Indian
Railways tariffs.
"""
from dataclasses import dataclass, fields

import numpy as np
import pandas as pd

import config

MODEL_RESULT_LABEL = config.MODEL_RESULT_LABEL


@dataclass
class CostParams:
    rake_capacity_t: float = 4000
    safety_buffer_pct: float = 0.08
    base_cost_per_rake_per_day: float = 8000
    spot_cost_per_rake_per_trip: float = 15000
    demurrage_cost_per_rake_per_day: float = 6000
    shortage_cost_per_tonne: float = 150
    spot_availability_cap_rakes_per_day: float = 16
    min_service_level_pct: float = 0.95

    @classmethod
    def from_overrides(cls, overrides: dict | None = None) -> "CostParams":
        overrides = overrides or {}
        valid_keys = {f.name for f in fields(cls)}
        kwargs = {k: float(v) for k, v in overrides.items() if k in valid_keys and v is not None}
        return cls(**kwargs)

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def cost_breakdown_for_B(B: float, required_rakes: np.ndarray, params: CostParams) -> dict:
    required_rakes = np.asarray(required_rakes, dtype=float)
    n_days = len(required_rakes)

    spot = np.maximum(required_rakes - B, 0)
    idle = np.maximum(B - required_rakes, 0)
    shortfall = np.maximum(spot - params.spot_availability_cap_rakes_per_day, 0)
    unmet_tonnes = shortfall * params.rake_capacity_t

    base_fleet_cost = n_days * B * params.base_cost_per_rake_per_day
    spot_cost = float(spot.sum()) * params.spot_cost_per_rake_per_trip
    demurrage_cost = float(idle.sum()) * params.demurrage_cost_per_rake_per_day
    shortage_cost = float(unmet_tonnes.sum()) * params.shortage_cost_per_tonne
    total_cost = base_fleet_cost + spot_cost + demurrage_cost + shortage_cost

    service_level_pct = float((shortfall == 0).mean()) if n_days else 0.0

    return {
        "B": float(B),
        "n_days": int(n_days),
        "base_fleet_cost": float(base_fleet_cost),
        "spot_cost": float(spot_cost),
        "demurrage_cost": float(demurrage_cost),
        "shortage_cost": float(shortage_cost),
        "total_cost": float(total_cost),
        "avg_spot_rakes_per_day": float(spot.mean()) if n_days else 0.0,
        "avg_idle_rakes_per_day": float(idle.mean()) if n_days else 0.0,
        "avg_unmet_tonnes_per_day": float(unmet_tonnes.mean()) if n_days else 0.0,
        "total_unmet_tonnes": float(unmet_tonnes.sum()),
        "service_level_pct": service_level_pct,
        "spot_dependency_pct": float(spot.sum() / required_rakes.sum()) if required_rakes.sum() else 0.0,
        "label": MODEL_RESULT_LABEL,
    }


def total_cost_curve(required_rakes: np.ndarray, params: CostParams, B_range: np.ndarray) -> pd.DataFrame:
    """Vectorized evaluation of Total(B) across an array of B values."""
    required_rakes = np.asarray(required_rakes, dtype=float)
    B_range = np.asarray(B_range, dtype=float)
    n_days = len(required_rakes)

    req = required_rakes[:, None]
    B = B_range[None, :]

    spot = np.maximum(req - B, 0)
    idle = np.maximum(B - req, 0)
    shortfall = np.maximum(spot - params.spot_availability_cap_rakes_per_day, 0)
    unmet_tonnes = shortfall * params.rake_capacity_t

    base_fleet_cost = n_days * B_range * params.base_cost_per_rake_per_day
    spot_sum = spot.sum(axis=0)
    spot_cost = spot_sum * params.spot_cost_per_rake_per_trip
    demurrage_cost = idle.sum(axis=0) * params.demurrage_cost_per_rake_per_day
    shortage_cost = unmet_tonnes.sum(axis=0) * params.shortage_cost_per_tonne
    total_cost = base_fleet_cost + spot_cost + demurrage_cost + shortage_cost
    service_level_pct = (shortfall == 0).mean(axis=0)
    required_total = required_rakes.sum()
    spot_dependency_pct = (spot_sum / required_total) if required_total else np.zeros_like(spot_sum)

    return pd.DataFrame({
        "B": B_range,
        "base_fleet_cost": base_fleet_cost,
        "spot_cost": spot_cost,
        "demurrage_cost": demurrage_cost,
        "shortage_cost": shortage_cost,
        "total_cost": total_cost,
        "service_level_pct": service_level_pct,
        "spot_dependency_pct": spot_dependency_pct,
    })

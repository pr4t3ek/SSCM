"""Base Fleet Capacity optimization.

Decision variable: B = Base Fleet Capacity (rakes/day).
Total(B) is a finite sum of max(linear, 0) hinge terms plus a linear term in
B, so it is piecewise-linear in B. A piecewise-linear function attains its
minimum over a bounded interval at a breakpoint or an endpoint, so enumerating
every breakpoint is exact. The breakpoints are the sorted union, across all
days, of {Required(t)}, {Required(t) - spot_availability_cap} and
{Required(t) + demurrage_free_idle} -- the last family coming from the
two-tier (free-allowance then punitive) demurrage charge; see
`candidate_breakpoints_array`.

Total(B) is additionally *convex* whenever the punitive demurrage rate is >=
the normal rate, which is the intended configuration: demurrage is then a
convex non-decreasing function of Idle(t), itself convex in B. Exactness of
the search does not depend on that -- it needs only piecewise-linearity and a
complete breakpoint set -- but the convexity claim made on Appendix A5 does.

We therefore solve exactly via breakpoint enumeration rather than a general
`scipy.optimize` search or OR-Tools: for ~300-365 days this is O(N) candidate
points x O(N) vectorized cost evaluation, comfortably fast enough to
recompute on every What-If Simulator slider change, and -- unlike a grid
search -- it is not an approximation, it is the exact minimum. There is no
combinatorial/integer structure here that would justify OR-Tools; SciPy is
still used (see `scripts` / tests) for a bounded `minimize_scalar` sanity
cross-check against this result during development, never in the hot path.

Min-service-level and the spot-availability cap are treated as *soft*
targets reported alongside the cost-optimal point rather than hard
constraints baked into the objective -- this is what surfaces the
"cost-optimal B leaves you at 91% service level; reaching 95% costs an
extra Rs X" trade-off on the Cost Optimization / Recommendation screens.
"""
from dataclasses import dataclass, replace
from typing import Optional

import numpy as np
import pandas as pd

import config
from models.cost_model import CostParams, cost_breakdown_for_B, total_cost_curve


@dataclass
class OptimizationResult:
    cost_optimal_B: float
    cost_optimal_breakdown: dict
    service_level_optimal_B: float
    service_level_optimal_breakdown: dict
    recommended_B: float
    recommended_breakdown: dict
    feasibility_warning: Optional[str]
    baseline_all_spot: dict
    savings_vs_baseline: dict
    cost_curve: pd.DataFrame
    candidate_breakpoints: pd.DataFrame


def candidate_breakpoints_array(
    required_rakes: np.ndarray,
    spot_cap: float,
    B_max: float,
    demurrage_free_idle: float = 0.0,
) -> np.ndarray:
    """Every B at which some hinge term in Total(B) changes slope.

    Three families, one per hinge:
      Required(t)                        -- spot/idle switchover
      Required(t) - spot_cap             -- shortage kicks in
      Required(t) + demurrage_free_idle  -- idle crosses the free allowance
                                            into the punitive demurrage tier

    Omitting the third family would leave breakpoint enumeration blind to the
    punitive-tier kinks and it would no longer be exact.
    """
    return np.unique(np.concatenate([
        required_rakes,
        np.clip(required_rakes - spot_cap, 0, None),
        np.clip(required_rakes + demurrage_free_idle, 0, B_max),
        [0.0, B_max],
    ]))


def optimize_base_fleet(required_rakes: np.ndarray, params: CostParams) -> OptimizationResult:
    required_rakes = np.asarray(required_rakes, dtype=float)
    B_max = float(required_rakes.max()) * 1.3 if len(required_rakes) else 1.0

    breakpoints = candidate_breakpoints_array(
        required_rakes,
        params.spot_availability_cap_rakes_per_day,
        B_max,
        params.demurrage_free_idle_rakes_per_day,
    )
    curve_at_breakpoints = total_cost_curve(required_rakes, params, breakpoints)

    best_idx = curve_at_breakpoints["total_cost"].idxmin()
    cost_optimal_B = float(curve_at_breakpoints.loc[best_idx, "B"])
    cost_optimal_breakdown = cost_breakdown_for_B(cost_optimal_B, required_rakes, params)

    meets_target = curve_at_breakpoints[curve_at_breakpoints["service_level_pct"] >= params.min_service_level_pct]
    feasibility_warning = None
    if not meets_target.empty:
        service_level_optimal_B = float(meets_target["B"].min())
    else:
        service_level_optimal_B = B_max
        feasibility_warning = (
            f"Even at B={B_max:.1f} rakes/day the {params.min_service_level_pct * 100:.0f}% "
            "service-level target is not reached under the current wagon-availability assumption."
        )
    service_level_optimal_breakdown = cost_breakdown_for_B(service_level_optimal_B, required_rakes, params)

    if cost_optimal_breakdown["service_level_pct"] >= params.min_service_level_pct:
        recommended_B = cost_optimal_B
    else:
        recommended_B = service_level_optimal_B
    recommended_breakdown = cost_breakdown_for_B(recommended_B, required_rakes, params)

    baseline_all_spot = cost_breakdown_for_B(0.0, required_rakes, params)
    savings_abs = baseline_all_spot["total_cost"] - recommended_breakdown["total_cost"]
    savings_pct = (savings_abs / baseline_all_spot["total_cost"]) if baseline_all_spot["total_cost"] else 0.0

    smooth_B = np.linspace(0, B_max, 200)
    cost_curve = total_cost_curve(required_rakes, params, smooth_B)

    return OptimizationResult(
        cost_optimal_B=cost_optimal_B,
        cost_optimal_breakdown=cost_optimal_breakdown,
        service_level_optimal_B=service_level_optimal_B,
        service_level_optimal_breakdown=service_level_optimal_breakdown,
        recommended_B=recommended_B,
        recommended_breakdown=recommended_breakdown,
        feasibility_warning=feasibility_warning,
        baseline_all_spot=baseline_all_spot,
        savings_vs_baseline={"absolute": savings_abs, "pct": savings_pct},
        cost_curve=cost_curve,
        candidate_breakpoints=curve_at_breakpoints,
    )


def run_sensitivity_grid(
    required_rakes: np.ndarray,
    params: CostParams,
    demand_growth_values,
    availability_multiplier_values,
    peak_reference: Optional[float] = None,
) -> pd.DataFrame:
    """Long-form grid: for each (demand growth, wagon availability) pair, the
    cost-optimal Base Fleet (rakes, and as % of the unscaled peak requirement).
    """
    required_rakes = np.asarray(required_rakes, dtype=float)
    peak_reference = peak_reference or float(required_rakes.max())

    rows = []
    for dg in demand_growth_values:
        scaled_required = required_rakes * (1 + dg)
        for av in availability_multiplier_values:
            scaled_params = replace(
                params,
                spot_availability_cap_rakes_per_day=params.spot_availability_cap_rakes_per_day * av,
            )
            opt = optimize_base_fleet(scaled_required, scaled_params)
            rows.append({
                "demand_growth_pct": dg,
                "availability_pct": av,
                "optimal_B": opt.cost_optimal_B,
                "optimal_B_pct": (opt.cost_optimal_B / peak_reference * 100) if peak_reference else 0.0,
                "min_total_cost": opt.cost_optimal_breakdown["total_cost"],
                "service_level_pct": opt.cost_optimal_breakdown["service_level_pct"],
            })
    return pd.DataFrame(rows)


TORNADO_VARIABLES = [
    {"key": "demand_growth_pct", "label": "Demand Growth", "kind": "demand"},
    {"key": "spot_cost_per_rake_per_trip", "label": "Spot Rake Cost", "kind": "param"},
    {"key": "base_cost_per_rake_per_day", "label": "Base Fleet Cost", "kind": "param"},
    {"key": "spot_availability_cap_rakes_per_day", "label": "Wagon Availability", "kind": "param"},
    {"key": "demurrage_cost_per_rake_per_day", "label": "Demurrage Cost", "kind": "param"},
    {"key": "demurrage_penalty_cost_per_rake_per_day", "label": "Punitive Demurrage", "kind": "param"},
    {"key": "shortage_cost_per_tonne", "label": "Shortage Penalty", "kind": "param"},
]


def run_tornado(required_rakes: np.ndarray, params: CostParams, B: Optional[float] = None) -> pd.DataFrame:
    """Cost swing at the recommended Base Fleet level as each assumption is
    independently pushed to its configured min/max, holding all others fixed.
    """
    required_rakes = np.asarray(required_rakes, dtype=float)
    if B is None:
        B = optimize_base_fleet(required_rakes, params).recommended_B
    base_cost = cost_breakdown_for_B(B, required_rakes, params)["total_cost"]

    rows = []
    for var in TORNADO_VARIABLES:
        spec = config.DEFAULT_PARAMS[var["key"]]
        low, high = spec["min"], spec["max"]
        if var["kind"] == "demand":
            cost_low = cost_breakdown_for_B(B, required_rakes * (1 + low), params)["total_cost"]
            cost_high = cost_breakdown_for_B(B, required_rakes * (1 + high), params)["total_cost"]
        else:
            params_low = replace(params, **{var["key"]: low})
            params_high = replace(params, **{var["key"]: high})
            cost_low = cost_breakdown_for_B(B, required_rakes, params_low)["total_cost"]
            cost_high = cost_breakdown_for_B(B, required_rakes, params_high)["total_cost"]
        rows.append({
            "key": var["key"],
            "label": var["label"],
            "base_cost": base_cost,
            "low_value": low,
            "high_value": high,
            "cost_at_low": cost_low,
            "cost_at_high": cost_high,
            "swing": abs(cost_high - cost_low),
        })
    return pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)


def run_risk_curve(required_rakes: np.ndarray, params: CostParams, B_values) -> pd.DataFrame:
    """Base Fleet Capacity vs. shortage probability / expected unmet demand."""
    required_rakes = np.asarray(required_rakes, dtype=float)
    rows = []
    for B in B_values:
        bd = cost_breakdown_for_B(float(B), required_rakes, params)
        rows.append({
            "B": float(B),
            "shortage_probability_pct": 1 - bd["service_level_pct"],
            "expected_unmet_tonnes_per_day": bd["avg_unmet_tonnes_per_day"],
            "expected_cost": bd["total_cost"],
        })
    return pd.DataFrame(rows)

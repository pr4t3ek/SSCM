"""Orchestrates models/* into JSON-ready responses for the optimize,
simulate, scenarios and sensitivity endpoints.

Stateless by design: every call receives the full set of parameter
overrides explicitly (the frontend keeps the authoritative copy in
`localStorage` via assumptions-store.js) rather than relying on server
session state.
"""
from dataclasses import replace

import numpy as np

import config
from models.cost_model import CostParams, cost_breakdown_for_B
from models.optimization import optimize_base_fleet, run_sensitivity_grid, run_tornado, run_risk_curve
from models.wagon_model import daily_requirement_series
from services.data_loader import get_dataset
from services.json_utils import json_safe
from services.scenario_engine import run_scenarios


def _required_rakes(overrides: dict, demand_growth_pct: float | None = None):
    """`demand_growth_pct=None` (the default) picks up whatever demand-growth
    assumption is in `overrides` (e.g. saved on the Assumptions page or sent
    by the Simulator's own slider). Sensitivity sweeps its own explicit
    demand-growth range and passes a fixed value here instead, so a saved
    baseline assumption doesn't silently compound with the sweep.
    """
    bundle = get_dataset()
    if demand_growth_pct is None:
        demand_growth_pct = overrides.get("demand_growth_pct", 0.0)
    rake_capacity_t = overrides.get("rake_capacity_t", config.DEFAULT_PARAMS["rake_capacity_t"]["value"])
    safety_buffer_pct = overrides.get("safety_buffer_pct", config.DEFAULT_PARAMS["safety_buffer_pct"]["value"])
    daily = daily_requirement_series(
        bundle.dated, tonnage_basis="demand", rake_capacity_t=rake_capacity_t, safety_buffer_pct=safety_buffer_pct
    )
    required = daily["required_rakes"].values * (1 + demand_growth_pct)
    return required, daily


def _effective_params(overrides: dict) -> CostParams:
    wagon_availability_pct = overrides.get(
        "wagon_availability_pct", config.DEFAULT_PARAMS["wagon_availability_pct"]["value"]
    )
    field_names = set(CostParams.__dataclass_fields__.keys())
    base_kwargs = {
        key: overrides.get(key, spec["value"])
        for key, spec in config.DEFAULT_PARAMS.items()
        if key in field_names
    }
    params = CostParams(**base_kwargs)
    return replace(
        params,
        spot_availability_cap_rakes_per_day=params.spot_availability_cap_rakes_per_day * wagon_availability_pct,
    )


def _serialize_optimization_result(result) -> dict:
    curve = result.cost_curve
    return {
        "cost_optimal_B": result.cost_optimal_B,
        "cost_optimal_breakdown": result.cost_optimal_breakdown,
        "service_level_optimal_B": result.service_level_optimal_B,
        "service_level_optimal_breakdown": result.service_level_optimal_breakdown,
        "recommended_B": result.recommended_B,
        "recommended_breakdown": result.recommended_breakdown,
        "feasibility_warning": result.feasibility_warning,
        "baseline_all_spot": result.baseline_all_spot,
        "savings_vs_baseline": result.savings_vs_baseline,
        "cost_curve": {
            "B": curve["B"].tolist(),
            "total_cost": curve["total_cost"].tolist(),
            "base_fleet_cost": curve["base_fleet_cost"].tolist(),
            "spot_cost": curve["spot_cost"].tolist(),
            "demurrage_cost": curve["demurrage_cost"].tolist(),
            "shortage_cost": curve["shortage_cost"].tolist(),
            "service_level_pct": curve["service_level_pct"].tolist(),
            "spot_dependency_pct": curve["spot_dependency_pct"].tolist(),
        },
        "candidate_breakpoints": {
            "count": int(len(result.candidate_breakpoints)),
            "rows": result.candidate_breakpoints[["B", "total_cost", "service_level_pct"]].to_dict(orient="records"),
        },
        "label": config.MODEL_RESULT_LABEL,
    }


def _required_summary(required: np.ndarray) -> dict:
    return {
        "avg": float(required.mean()) if len(required) else 0.0,
        "peak": float(required.max()) if len(required) else 0.0,
    }


def optimize(overrides: dict) -> dict:
    required, _ = _required_rakes(overrides)
    params = _effective_params(overrides)
    result = optimize_base_fleet(required, params)
    payload = _serialize_optimization_result(result)
    payload["required_summary"] = _required_summary(required)
    return json_safe(payload)


def simulate(overrides: dict) -> dict:
    required, _ = _required_rakes(overrides)
    params = _effective_params(overrides)
    result = optimize_base_fleet(required, params)
    payload = _serialize_optimization_result(result)
    payload["required_summary"] = _required_summary(required)

    manual_B = overrides.get("B_manual_override")
    if manual_B is not None:
        payload["manual_breakdown"] = cost_breakdown_for_B(float(manual_B), required, params)

    return json_safe(payload)


def scenarios(overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    required, _ = _required_rakes(overrides)
    params = _effective_params(overrides)
    return json_safe(run_scenarios(required, params))


def sensitivity(kind: str, detail: bool = False, overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    # Sensitivity sweeps its own explicit demand-growth range (see below), so
    # the baseline required-rakes series is pinned to 0% growth here -- a
    # saved Assumptions-page growth figure must not silently compound with it.
    required, _ = _required_rakes(overrides, demand_growth_pct=0.0)
    params = _effective_params(overrides)

    if kind == "heatmap":
        dg_values = list(np.linspace(-0.10, 0.30, 9 if detail else 5))
        av_values = list(np.linspace(0.70, 1.00, 7 if detail else 4))
        grid = run_sensitivity_grid(required, params, dg_values, av_values, peak_reference=float(required.max()))
        pivot_B_pct = grid.pivot(index="demand_growth_pct", columns="availability_pct", values="optimal_B_pct")
        pivot_cost = grid.pivot(index="demand_growth_pct", columns="availability_pct", values="min_total_cost")
        pivot_service = grid.pivot(index="demand_growth_pct", columns="availability_pct", values="service_level_pct")
        return json_safe({
            "demand_growth_pct": pivot_B_pct.index.tolist(),
            "availability_pct": pivot_B_pct.columns.tolist(),
            "optimal_B_pct": pivot_B_pct.values.tolist(),
            "min_total_cost": pivot_cost.values.tolist(),
            "service_level_pct": pivot_service.values.tolist(),
            "label": config.MODEL_RESULT_LABEL,
        })

    if kind == "tornado":
        df = run_tornado(required, params)
        return json_safe({"parameters": df.to_dict(orient="records"), "label": config.MODEL_RESULT_LABEL})

    if kind == "risk":
        B_max = float(required.max()) * 1.3
        B_values = np.linspace(0, B_max, 25 if not detail else 50)
        df = run_risk_curve(required, params, B_values)
        return json_safe({
            "B_values": df["B"].tolist(),
            "shortage_probability_pct": df["shortage_probability_pct"].tolist(),
            "expected_unmet_tonnes_per_day": df["expected_unmet_tonnes_per_day"].tolist(),
            "expected_cost": df["expected_cost"].tolist(),
            "label": config.MODEL_RESULT_LABEL,
        })

    raise ValueError(f"Unknown sensitivity kind: {kind}")

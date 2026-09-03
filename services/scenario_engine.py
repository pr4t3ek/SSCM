"""Three preconfigured strategic scenarios along the Base-vs-Spot spectrum."""
import numpy as np

from models.cost_model import cost_breakdown_for_B
from models.optimization import optimize_base_fleet

SCENARIO_DEFS = [
    {"key": "spot_heavy", "name": "Spot Heavy", "description": "Low base fleet, high spot dependence.", "percentile": 25},
    {"key": "balanced", "name": "Balanced (Recommended)", "description": "Cost-optimal base fleet from the optimization engine.", "percentile": None},
    {"key": "base_heavy", "name": "Base Heavy", "description": "High base fleet, low spot dependence.", "percentile": 90},
]


def run_scenarios(required_rakes, params) -> dict:
    required_rakes = np.asarray(required_rakes, dtype=float)
    optimal = optimize_base_fleet(required_rakes, params)

    scenarios = []
    for sdef in SCENARIO_DEFS:
        B = optimal.recommended_B if sdef["percentile"] is None else float(np.percentile(required_rakes, sdef["percentile"]))
        breakdown = cost_breakdown_for_B(B, required_rakes, params)
        fleet_utilization_pct = (1 - breakdown["avg_idle_rakes_per_day"] / B) * 100 if B > 0 else 0.0
        scenarios.append({
            "key": sdef["key"],
            "name": sdef["name"],
            "description": sdef["description"],
            "B_rakes": B,
            "fleet_utilization_pct": fleet_utilization_pct,
            **breakdown,
        })

    return {"scenarios": scenarios, "recommended_key": "balanced"}

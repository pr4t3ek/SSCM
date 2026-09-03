"""Central configuration: paths, screen registries, and default model parameters.

Sidebar navigation (both the Jinja nav and the JS keyboard-navigation array) is
driven from MAIN_SCREENS / APPENDIX_SCREENS below so there is a single source
of truth for slugs, routes, and titles.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_XLSX_PATH = os.path.join(DATA_DIR, "raw", "Lakhanpur_Area_Shiftwise_Coal_Data.xlsx")
CLEAN_CSV_PATH = os.path.join(DATA_DIR, "lakhanpur_shift_data.csv")

HOST = os.environ.get("SSCM_HOST", "127.0.0.1")
PORT = int(os.environ.get("SSCM_PORT", "5000"))
DEBUG = os.environ.get("SSCM_DEBUG", "1") == "1"

MODEL_RESULT_LABEL = "Model-based result using configured assumptions."

# Ordered (number, slug, title, template, endpoint) tuples for the 12 MAIN
# presentation screens and the 8 APPENDIX / ANALYTICS screens. `number` is the
# two-digit MAIN sequence used for keyboard navigation; appendix screens use
# an "A"-prefixed code instead.
MAIN_SCREENS = [
    {"code": "01", "slug": "overview", "title": "Executive Summary", "short": "Executive Summary", "template": "overview.html"},
    {"code": "02", "slug": "problem", "title": "Business Problem", "short": "Business Problem", "template": "problem.html"},
    {"code": "03", "slug": "demand-dispatch", "title": "Demand-Dispatch Gap", "short": "Demand-Dispatch", "template": "demand_dispatch.html"},
    {"code": "04", "slug": "shifts", "title": "Shift & Operational Diagnosis", "short": "Shift Diagnosis", "template": "shifts.html"},
    {"code": "05", "slug": "wagon", "title": "Wagon Requirement", "short": "Wagon Requirement", "template": "wagon.html"},
    {"code": "06", "slug": "fleet-strategy", "title": "Base vs Spot Fleet Strategy", "short": "Fleet Strategy", "template": "fleet_strategy.html"},
    {"code": "07", "slug": "cost-optimization", "title": "Cost Optimization", "short": "Cost Optimization", "template": "optimization.html"},
    {"code": "08", "slug": "simulator", "title": "What-If Simulator", "short": "Strategy Simulator", "template": "simulator.html"},
    {"code": "09", "slug": "scenarios", "title": "Scenario Comparison", "short": "Scenario Analysis", "template": "scenarios.html"},
    {"code": "10", "slug": "sensitivity", "title": "Sensitivity & Risk", "short": "Sensitivity & Risk", "template": "sensitivity.html"},
    {"code": "11", "slug": "recommendation", "title": "Final Recommendation", "short": "Recommendation", "template": "recommendation.html"},
    {"code": "12", "slug": "takeaways", "title": "Management Takeaways", "short": "Takeaways", "template": "takeaways.html"},
]

APPENDIX_SCREENS = [
    {"code": "A1", "slug": "data-explorer", "title": "Data Explorer", "template": "appendix/data_explorer.html"},
    {"code": "A2", "slug": "shift-detail", "title": "Detailed Shift Analytics", "template": "appendix/shift_detail.html"},
    {"code": "A3", "slug": "assumptions", "title": "Assumptions & Parameters", "template": "appendix/assumptions.html"},
    {"code": "A4", "slug": "cost-model", "title": "Cost Model", "template": "appendix/cost_model.html"},
    {"code": "A5", "slug": "methodology", "title": "Optimization Methodology", "template": "appendix/methodology.html"},
    {"code": "A6", "slug": "sensitivity-detail", "title": "Detailed Sensitivity", "template": "appendix/sensitivity_detail.html"},
    {"code": "A7", "slug": "optimization-output", "title": "Optimization Output", "template": "appendix/optimization_output.html"},
    {"code": "A8", "slug": "data-quality", "title": "Data Quality", "template": "appendix/data_quality.html"},
]

ALL_SCREENS_BY_SLUG = {s["slug"]: s for s in MAIN_SCREENS + APPENDIX_SCREENS}

# --- Default cost / optimization parameters -------------------------------
# Provenance:
#   EXTERNAL  = a real figure taken from the team's proposal (rake capacity)
#   ASSUMPTION = an illustrative, user-editable planning figure -- NOT an
#                official CIL / Indian Railways tariff. Every model output
#                built from these must carry MODEL_RESULT_LABEL.
DEFAULT_PARAMS = {
    "rake_capacity_t": {
        "value": 4000, "min": 2500, "max": 5500, "step": 100,
        "unit": "tonnes/rake", "provenance": "EXTERNAL",
        "label": "Rake Capacity",
        "description": "Payload per rake, per the project proposal (~4,000 t).",
        "simulator_visible": False,
    },
    "safety_buffer_pct": {
        "value": 0.08, "min": 0.0, "max": 0.25, "step": 0.01,
        "unit": "fraction", "provenance": "ASSUMPTION",
        "label": "Safety Buffer",
        "description": "Extra capacity margin added on top of raw tonnage requirement.",
        "simulator_visible": False,
    },
    "base_cost_per_rake_per_day": {
        "value": 8000, "min": 2000, "max": 20000, "step": 500,
        "unit": "Rs/rake/day", "provenance": "ASSUMPTION",
        "label": "Base Fleet Cost",
        "description": "Fixed daily cost of one captive/leased (GPWIS/SFTO) rake, illustrative.",
        "simulator_visible": True,
    },
    "spot_cost_per_rake_per_trip": {
        "value": 15000, "min": 5000, "max": 40000, "step": 500,
        "unit": "Rs/rake/trip", "provenance": "ASSUMPTION",
        "label": "Spot Rake Cost",
        "description": "Variable cost of one spot FOIS rake booking, illustrative.",
        "simulator_visible": True,
    },
    "demurrage_cost_per_rake_per_day": {
        "value": 6000, "min": 1000, "max": 20000, "step": 500,
        "unit": "Rs/rake/day", "provenance": "ASSUMPTION",
        "label": "Demurrage Cost",
        "description": "Normal-rate cost of an idle/overcommitted base-fleet rake on a low-demand day, illustrative.",
        "simulator_visible": True,
    },
    "demurrage_free_idle_rakes_per_day": {
        "value": 2.0, "min": 0.0, "max": 10.0, "step": 0.5,
        "unit": "rakes/day", "provenance": "ASSUMPTION",
        "label": "Demurrage Free Allowance",
        "description": (
            "Idle base-fleet rakes tolerated per day at the normal demurrage rate. Idle capacity "
            "beyond this is charged the punitive rate instead, mirroring the free-time-then-penal "
            "structure of Indian Railways demurrage, illustrative."
        ),
        "simulator_visible": True,
    },
    "demurrage_penalty_cost_per_rake_per_day": {
        "value": 12000, "min": 2000, "max": 40000, "step": 500,
        "unit": "Rs/rake/day", "provenance": "ASSUMPTION",
        "label": "Punitive Demurrage Rate",
        "description": (
            "Higher rate charged on idle base-fleet rakes above the free allowance, illustrative. "
            "Keep it at or above the normal demurrage rate: a lower value makes the cost curve "
            "non-convex (the optimizer stays exact either way, but the convexity claim on A5 does not)."
        ),
        "simulator_visible": True,
    },
    "shortage_cost_per_tonne": {
        "value": 150, "min": 20, "max": 500, "step": 10,
        "unit": "Rs/tonne", "provenance": "ASSUMPTION",
        "label": "Shortage Penalty",
        "description": "Penalty cost per tonne of demand left unmet after the spot market is exhausted, illustrative.",
        "simulator_visible": True,
    },
    "spot_availability_cap_rakes_per_day": {
        "value": 16, "min": 8, "max": 30, "step": 1,
        "unit": "rakes/day", "provenance": "ASSUMPTION",
        "label": "Nominal Spot Rake Capacity",
        "description": (
            "Maximum spot rakes Indian Railways can realistically supply per day at 100% "
            "availability, illustrative -- calibrated near the dataset's own implied historical "
            "rake throughput (avg dispatch / rake capacity)."
        ),
        "simulator_visible": False,
    },
    "wagon_availability_pct": {
        "value": 1.00, "min": 0.70, "max": 1.00, "step": 0.01,
        "unit": "fraction", "provenance": "ASSUMPTION",
        "label": "Wagon Availability",
        "description": "Fraction of nominal spot-rake capacity actually available that day (IR congestion, maintenance, etc.).",
        "simulator_visible": True,
    },
    "min_service_level_pct": {
        "value": 0.95, "min": 0.80, "max": 0.99, "step": 0.01,
        "unit": "fraction", "provenance": "ASSUMPTION",
        "label": "Service Level Target",
        "description": "Target fraction of days with fully met spot demand (soft target, reported not enforced).",
        "simulator_visible": True,
    },
    "demand_growth_pct": {
        "value": 0.0, "min": -0.10, "max": 0.30, "step": 0.01,
        "unit": "fraction", "provenance": "ASSUMPTION",
        "label": "Demand Growth",
        "description": "Uniform scaling applied to historical daily demand for what-if analysis.",
        "simulator_visible": True,
    },
}

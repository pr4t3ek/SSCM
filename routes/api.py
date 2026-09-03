"""Read-mostly JSON API: observed-data analytics, data quality, insights,
the data explorer, and the editable-assumptions catalog.

POST endpoints (optimize/simulate) live in routes/optimization.py.
"""
from flask import Blueprint, jsonify, request

import config
from services import analytics, insight_generator, optimization_service
from services.data_loader import get_dataset
from services.json_utils import json_safe

api_bp = Blueprint("api", __name__)


def _bool_arg(name, default=False):
    val = request.args.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


def _overrides_from_query() -> dict:
    """Pick up any configured assumption keys present in the query string
    (used by GET endpoints so a saved Assumptions edit actually changes what
    Cost Optimization / Scenario / Sensitivity screens compute).
    """
    overrides = {}
    for key in config.DEFAULT_PARAMS:
        val = request.args.get(key)
        if val not in (None, ""):
            overrides[key] = float(val)
    return overrides


@api_bp.route("/kpis")
def kpis():
    bundle = get_dataset()
    return jsonify(json_safe(analytics.compute_kpis(bundle)))


@api_bp.route("/demand-dispatch")
def demand_dispatch():
    bundle = get_dataset()
    freq = request.args.get("freq", "D").upper()
    if freq not in ("D", "W", "M"):
        freq = "D"
    return jsonify(json_safe(analytics.demand_dispatch_series(bundle, freq=freq)))


@api_bp.route("/shift-analysis")
def shift_analysis():
    bundle = get_dataset()
    detail = _bool_arg("detail", False)
    return jsonify(json_safe(analytics.shift_analysis(bundle, detail=detail)))


@api_bp.route("/wagon-requirement")
def wagon_requirement():
    bundle = get_dataset()
    tonnage_basis = request.args.get("tonnage_basis", "demand")
    rake_capacity_t = float(request.args.get("rake_capacity", config.DEFAULT_PARAMS["rake_capacity_t"]["value"]))
    safety_buffer_pct = float(request.args.get("safety_buffer", config.DEFAULT_PARAMS["safety_buffer_pct"]["value"]))
    freq = request.args.get("freq", "D").upper()
    if freq not in ("D", "W", "M"):
        freq = "D"
    view = analytics.wagon_requirement_view(
        bundle, tonnage_basis=tonnage_basis, rake_capacity_t=rake_capacity_t,
        safety_buffer_pct=safety_buffer_pct, freq=freq,
    )
    return jsonify(json_safe(view))


@api_bp.route("/contract-portfolio")
def contract_portfolio():
    """Four-tier contract sizing + the data-derived season profile it rests on.

    Percentile-derived, so it deliberately does NOT depend on the optimization
    engine and moves no cost figure on any other screen.
    """
    bundle = get_dataset()
    rake_capacity_t = float(request.args.get("rake_capacity", config.DEFAULT_PARAMS["rake_capacity_t"]["value"]))
    safety_buffer_pct = float(request.args.get("safety_buffer", config.DEFAULT_PARAMS["safety_buffer_pct"]["value"]))
    return jsonify(json_safe(analytics.contract_portfolio(
        bundle, rake_capacity_t=rake_capacity_t, safety_buffer_pct=safety_buffer_pct)))


@api_bp.route("/scenarios")
def scenarios():
    return jsonify(json_safe(optimization_service.scenarios(_overrides_from_query())))


@api_bp.route("/sensitivity")
def sensitivity():
    kind = request.args.get("type", "heatmap")
    detail = _bool_arg("detail", False)
    if kind not in ("heatmap", "tornado", "risk"):
        return jsonify({"error": f"unknown sensitivity type '{kind}'"}), 400
    return jsonify(json_safe(optimization_service.sensitivity(kind, detail=detail, overrides=_overrides_from_query())))


@api_bp.route("/data-quality")
def data_quality():
    bundle = get_dataset()
    return jsonify(json_safe(bundle.data_quality))


@api_bp.route("/insights")
def insights():
    bundle = get_dataset()
    screen = request.args.get("screen", "executive_summary")

    if screen == "executive_summary":
        kpis_data = analytics.compute_kpis(bundle)
        dd = analytics.demand_dispatch_series(bundle, freq="D")
        result = insight_generator.build_executive_summary_insights(kpis_data, dd, bundle.data_quality)
    elif screen == "shift_diagnosis":
        sa = analytics.shift_analysis(bundle, detail=False)
        result = insight_generator.build_shift_diagnosis_insights(sa)
    elif screen == "wagon":
        wr = analytics.wagon_requirement_view(bundle)
        result = insight_generator.build_wagon_insights(wr)
    elif screen == "sensitivity":
        torn = optimization_service.sensitivity("tornado")
        risk = optimization_service.sensitivity("risk")
        result = insight_generator.build_sensitivity_insights(torn, risk)
    elif screen == "recommendation":
        opt = optimization_service.optimize({})
        result = insight_generator.build_recommendation_insights(opt)
    elif screen == "takeaways":
        kpis_data = analytics.compute_kpis(bundle)
        opt = optimization_service.optimize({})
        result = insight_generator.build_takeaways_insights(kpis_data, opt)
    else:
        result = []

    return jsonify({"insights": json_safe(result)})


@api_bp.route("/data-explorer")
def data_explorer():
    bundle = get_dataset()
    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 50)), 1000)
    filters = {
        "shift_number": request.args.get("shift_number"),
        "date_from": request.args.get("date_from"),
        "date_to": request.args.get("date_to"),
        "min_coal_demanded_t": request.args.get("min_demand"),
        "max_coal_demanded_t": request.args.get("max_demand"),
        "min_coal_produced_t": request.args.get("min_production"),
        "max_coal_produced_t": request.args.get("max_production"),
        "min_coal_dispatched_t": request.args.get("min_dispatch"),
        "max_coal_dispatched_t": request.args.get("max_dispatch"),
        "min_deficit_t": request.args.get("min_deficit"),
        "max_deficit_t": request.args.get("max_deficit"),
    }
    return jsonify(json_safe(analytics.data_explorer_rows(bundle, page=page, page_size=page_size, filters=filters)))


@api_bp.route("/assumptions/defaults")
def assumptions_defaults():
    parameters = [{"key": key, **spec} for key, spec in config.DEFAULT_PARAMS.items()]
    return jsonify({"parameters": json_safe(parameters)})

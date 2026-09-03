"""Turns already-computed analytics/optimization dicts into short, plain-
English insight strings. Every function reads live numbers -- nothing here
is a hardcoded statement -- and returns `None` when it has nothing to say.
"""


def insight_overall_deficit(kpis: dict):
    return (
        f"Demand exceeded dispatch in {kpis['pct_shifts_positive_deficit']:.0f}% of observed shifts, "
        f"averaging a {kpis['avg_deficit_per_shift_t']:,.0f}-tonne shortfall per shift."
    )


def insight_fulfilment_trend(demand_dispatch: dict):
    fulfilment = [f for f in demand_dispatch["fulfilment_pct"] if f is not None]
    if len(fulfilment) < 4:
        return None
    half = len(fulfilment) // 2
    first_half = sum(fulfilment[:half]) / half
    second_half = sum(fulfilment[half:]) / (len(fulfilment) - half)
    direction = "improved" if second_half > first_half else "worsened"
    return (
        f"Dispatch fulfilment has {direction} from {first_half:.1f}% (first half of the period) "
        f"to {second_half:.1f}% (second half)."
    )


def insight_weakest_shift(shift_analysis: dict):
    w = shift_analysis["weakest_shift"]
    return (
        f"The {w['shift_label']} shift has the lowest fulfilment at {w['fulfilment_pct']:.1f}%, "
        f"averaging a {w['avg_deficit']:,.0f}-tonne deficit and accounting for "
        f"{w['share_of_total_deficit_pct']:.0f}% of total observed deficit."
    )


def insight_wagon_peak(wagon_requirement: dict):
    s = wagon_requirement["summary"]
    return (
        f"Peak rake requirement reached {s['peak']:.1f} rakes/day on {s['peak_date']}, "
        f"{(s['peak'] / s['avg'] - 1) * 100:.0f}% above the {s['avg']:.1f} rakes/day average."
    )


def insight_optimal_split(optimize_result: dict):
    rec = optimize_result["recommended_breakdown"]
    savings = optimize_result["savings_vs_baseline"]
    return (
        f"A {rec['B']:.1f} rakes/day base fleet, backed by spot bookings for the remaining "
        f"{rec['spot_dependency_pct'] * 100:.0f}% of requirement, minimizes expected cost and saves "
        f"{savings['pct'] * 100:.0f}% versus relying on spot bookings alone."
    )


def insight_most_sensitive_assumption(tornado: dict):
    params = tornado.get("parameters") or []
    if not params:
        return None
    top = params[0]
    return (
        f"{top['label']} is the most sensitive assumption -- total cost swings by "
        f"Rs {top['swing']:,.0f} across its configured range, holding the base-fleet decision fixed."
    )


def insight_service_level_risk(risk: dict):
    probs = risk.get("shortage_probability_pct") or []
    if len(probs) < 2:
        return None
    return (
        f"Shortage probability falls from {probs[0] * 100:.0f}% with no base fleet to "
        f"{probs[-1] * 100:.0f}% at the highest base-fleet level tested -- base capacity is what "
        f"buys down risk, not spot access alone."
    )


def insight_data_quality_caveat(dq_report: dict):
    missing = dq_report.get("missing_date_rows") or []
    incomplete = dq_report.get("incomplete_days") or []
    if not missing and not incomplete:
        return None
    parts = []
    if missing:
        parts.append(f"{len(missing)} shift record(s) are missing a date")
    if incomplete:
        parts.append(f"{len(incomplete)} day(s) have fewer than the expected 3 recorded shifts")
    return "Data quality note: " + " and ".join(parts) + " -- see the Data Quality appendix for detail."


def build_executive_summary_insights(kpis, demand_dispatch, dq_report):
    insights = [insight_overall_deficit(kpis), insight_fulfilment_trend(demand_dispatch)]
    insights.append(insight_data_quality_caveat(dq_report))
    return [i for i in insights if i]


def build_shift_diagnosis_insights(shift_analysis):
    return [i for i in [insight_weakest_shift(shift_analysis)] if i]


def build_wagon_insights(wagon_requirement):
    return [i for i in [insight_wagon_peak(wagon_requirement)] if i]


def build_sensitivity_insights(tornado, risk):
    return [i for i in [insight_most_sensitive_assumption(tornado), insight_service_level_risk(risk)] if i]


def build_recommendation_insights(optimize_result):
    return [i for i in [insight_optimal_split(optimize_result)] if i]


def build_takeaways_insights(kpis, optimize_result):
    return [i for i in [insight_overall_deficit(kpis), insight_optimal_split(optimize_result)] if i]

"""Observed-data analytics: KPIs, demand/dispatch series, shift diagnostics,
wagon-requirement views and the data-explorer table. Everything here reads
from `services.data_loader.get_dataset()` and returns plain dicts ready for
`json_safe()` + `jsonify()` at the route layer.
"""
import numpy as np
import pandas as pd

from models.wagon_model import daily_requirement_series

FREQ_RESAMPLE = {"D": "D", "W": "W-MON", "M": "MS"}

FULFILMENT_GREEN = 95
FULFILMENT_AMBER = 85
HIGH_RISK_FULFILMENT_PCT = 80


def semantic_status(fulfilment_pct) -> str:
    if fulfilment_pct is None or (isinstance(fulfilment_pct, float) and np.isnan(fulfilment_pct)):
        return "neutral"
    if fulfilment_pct >= FULFILMENT_GREEN:
        return "green"
    if fulfilment_pct >= FULFILMENT_AMBER:
        return "amber"
    return "red"


def compute_kpis(bundle) -> dict:
    clean = bundle.clean
    dated = bundle.dated

    total_production_t = float(clean["coal_produced_t"].sum())
    total_demand_t = float(clean["coal_demanded_t"].sum())
    total_dispatch_t = float(clean["coal_dispatched_t"].sum())
    total_deficit_t = total_demand_t - total_dispatch_t
    fulfilment_pct = (total_dispatch_t / total_demand_t * 100) if total_demand_t else 0.0

    peak_row = clean.loc[clean["deficit_t"].idxmax()]
    high_risk_mask = clean["fulfilment_pct"] < HIGH_RISK_FULFILMENT_PCT

    return {
        "total_production_t": total_production_t,
        "total_demand_t": total_demand_t,
        "total_dispatch_t": total_dispatch_t,
        "total_deficit_t": total_deficit_t,
        "fulfilment_pct": fulfilment_pct,
        "fulfilment_status": semantic_status(fulfilment_pct),
        "avg_deficit_per_shift_t": float(clean["deficit_t"].mean()),
        "deficit_std_t": float(clean["deficit_t"].std()),
        "pct_shifts_positive_deficit": float(clean["is_deficit_positive"].mean() * 100),
        "peak_deficit_t": float(peak_row["deficit_t"]),
        "peak_deficit_date": peak_row["date"].strftime("%Y-%m-%d") if pd.notnull(peak_row["date"]) else None,
        "peak_deficit_shift": peak_row["shift_label"],
        "high_risk_shifts": int(high_risk_mask.sum()),
        "high_risk_shifts_pct": float(high_risk_mask.mean() * 100),
        "n_shifts": int(len(clean)),
        "n_days": int(dated["date"].nunique()),
        "date_range": bundle.data_quality["date_range"],
    }


def demand_dispatch_series(bundle, freq: str = "D") -> dict:
    daily = (
        bundle.dated.groupby("date", as_index=False)
        .agg(production=("coal_produced_t", "sum"), demand=("coal_demanded_t", "sum"), dispatch=("coal_dispatched_t", "sum"))
        .sort_values("date")
    )
    if freq != "D":
        daily = (
            daily.set_index("date")
            .resample(FREQ_RESAMPLE[freq])
            .sum()
            .reset_index()
        )
    daily["deficit"] = daily["demand"] - daily["dispatch"]
    daily["fulfilment_pct"] = np.where(daily["demand"] > 0, daily["dispatch"] / daily["demand"] * 100, np.nan)

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in daily["date"]],
        "production": daily["production"].tolist(),
        "demand": daily["demand"].tolist(),
        "dispatch": daily["dispatch"].tolist(),
        "deficit": daily["deficit"].tolist(),
        "fulfilment_pct": daily["fulfilment_pct"].tolist(),
        "freq": freq,
    }


def shift_analysis(bundle, detail: bool = False) -> dict:
    dated = bundle.dated
    grouped = (
        dated.groupby(["shift_number", "shift_label"], as_index=False)
        .agg(
            avg_production=("coal_produced_t", "mean"),
            avg_demand=("coal_demanded_t", "mean"),
            avg_dispatch=("coal_dispatched_t", "mean"),
            avg_deficit=("deficit_t", "mean"),
            n=("deficit_t", "size"),
        )
        .sort_values("shift_number")
    )
    grouped["fulfilment_pct"] = grouped["avg_dispatch"] / grouped["avg_demand"] * 100
    grouped["status"] = grouped["fulfilment_pct"].apply(semantic_status)
    grouped["share_of_total_deficit_pct"] = (
        grouped["avg_deficit"] * grouped["n"] / (dated["deficit_t"].sum()) * 100
    )
    shifts = grouped.to_dict(orient="records")
    weakest = min(shifts, key=lambda s: s["fulfilment_pct"])

    distribution = {
        row["shift_label"]: dated.loc[dated["shift_number"] == row["shift_number"], "deficit_t"].tolist()
        for row in shifts
    }

    result = {
        "shifts": shifts,
        "weakest_shift": {
            "shift_label": weakest["shift_label"],
            "fulfilment_pct": weakest["fulfilment_pct"],
            "avg_deficit": weakest["avg_deficit"],
            "share_of_total_deficit_pct": weakest["share_of_total_deficit_pct"],
        },
        "distribution": distribution,
    }

    if detail:
        heatmap = dated.pivot_table(index="date", columns="shift_label", values="deficit_t", aggfunc="mean")
        result["heatmap"] = {
            "dates": [d.strftime("%Y-%m-%d") for d in heatmap.index],
            "shift_labels": heatmap.columns.tolist(),
            "values": heatmap.values.tolist(),
        }
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heatmap_dow = (
            dated.pivot_table(index="day_of_week", columns="shift_label", values="deficit_t", aggfunc="mean")
            .reindex(dow_order)
        )
        result["heatmap_day_of_week"] = {
            "days": dow_order,
            "shift_labels": heatmap_dow.columns.tolist(),
            "values": heatmap_dow.values.tolist(),
        }

    return result


def wagon_requirement_view(
    bundle,
    tonnage_basis: str = "demand",
    rake_capacity_t: float = 4000,
    safety_buffer_pct: float = 0.08,
    freq: str = "D",
) -> dict:
    daily = daily_requirement_series(bundle.dated, tonnage_basis, rake_capacity_t, safety_buffer_pct)

    peak_idx = daily["required_rakes"].idxmax()
    summary = {
        "avg": float(daily["required_rakes"].mean()),
        "peak": float(daily.loc[peak_idx, "required_rakes"]),
        "peak_date": daily.loc[peak_idx, "date"].strftime("%Y-%m-%d"),
        "min": float(daily["required_rakes"].min()),
        "p25": float(np.percentile(daily["required_rakes"], 25)),
        "p50": float(np.percentile(daily["required_rakes"], 50)),
        "p75": float(np.percentile(daily["required_rakes"], 75)),
        "p90": float(np.percentile(daily["required_rakes"], 90)),
    }

    view = daily
    if freq != "D":
        view = (
            daily.set_index("date")[["total_tonnes", "required_rakes"]]
            .resample(FREQ_RESAMPLE[freq])
            .mean()
            .reset_index()
        )

    return {
        "timeseries": {
            "dates": [d.strftime("%Y-%m-%d") for d in view["date"]],
            "required_tonnes": view["total_tonnes"].tolist(),
            "required_rakes": view["required_rakes"].tolist(),
        },
        "summary": summary,
        "tonnage_basis": tonnage_basis,
        "rake_capacity_t": rake_capacity_t,
        "safety_buffer_pct": safety_buffer_pct,
    }


DATA_EXPLORER_COLUMNS = [
    "date", "shift_number", "shift_timing", "coal_produced_t",
    "coal_dispatched_t", "coal_demanded_t", "deficit_t", "fulfilment_pct",
]


def data_explorer_rows(bundle, page: int = 1, page_size: int = 50, filters: dict | None = None) -> dict:
    df = bundle.clean.copy()
    filters = filters or {}

    if filters.get("shift_number"):
        df = df[df["shift_number"] == int(filters["shift_number"])]
    if filters.get("date_from"):
        cutoff = pd.Timestamp(filters["date_from"])
        df = df[df["date"].isna() | (df["date"] >= cutoff)]
    if filters.get("date_to"):
        cutoff = pd.Timestamp(filters["date_to"])
        df = df[df["date"].isna() | (df["date"] <= cutoff)]
    for field in ("coal_demanded_t", "coal_produced_t", "coal_dispatched_t", "deficit_t"):
        min_key, max_key = f"min_{field}", f"max_{field}"
        if filters.get(min_key) not in (None, ""):
            df = df[df[field] >= float(filters[min_key])]
        if filters.get(max_key) not in (None, ""):
            df = df[df[field] <= float(filters[max_key])]

    total_rows = len(df)
    start = max(page - 1, 0) * page_size
    page_df = df.iloc[start:start + page_size]

    rows = []
    for _, row in page_df[DATA_EXPLORER_COLUMNS].iterrows():
        rows.append({
            "date": row["date"].strftime("%Y-%m-%d") if pd.notnull(row["date"]) else None,
            "shift_number": int(row["shift_number"]),
            "shift_timing": row["shift_timing"],
            "coal_produced_t": int(row["coal_produced_t"]),
            "coal_dispatched_t": int(row["coal_dispatched_t"]),
            "coal_demanded_t": int(row["coal_demanded_t"]),
            "deficit_t": int(row["deficit_t"]),
            "fulfilment_pct": None if pd.isna(row["fulfilment_pct"]) else float(row["fulfilment_pct"]),
        })

    return {
        "rows": rows,
        "total_rows": int(total_rows),
        "page": page,
        "page_size": page_size,
        "columns": DATA_EXPLORER_COLUMNS,
    }


# --- Seasonality & contract portfolio -------------------------------------
# A month is classified PEAK / LEAN when its mean daily rake requirement sits
# more than SEASON_THRESHOLD_PCT above / below the all-period mean. Nothing is
# keyed to a specific calendar month: on a flat dataset every month lands in
# SHOULDER and the screens correctly report no seasonality at all.
SEASON_THRESHOLD_PCT = 0.05

SEASON_DEFS = [
    {"key": "lean", "label": "Lean"},
    {"key": "shoulder", "label": "Shoulder"},
    {"key": "peak", "label": "Peak"},
]


def season_profile(
    bundle,
    rake_capacity_t: float = 4000,
    safety_buffer_pct: float = 0.08,
    threshold_pct: float = SEASON_THRESHOLD_PCT,
) -> dict:
    """Classify each calendar month as lean / shoulder / peak from the data."""
    daily = daily_requirement_series(bundle.dated, "demand", rake_capacity_t, safety_buffer_pct).copy()
    daily["month_period"] = daily["date"].dt.strftime("%Y-%m")
    overall_mean = float(daily["required_rakes"].mean())

    monthly = (
        daily.groupby("month_period", as_index=False)
        .agg(mean_required=("required_rakes", "mean"), n_days=("required_rakes", "size"))
        .sort_values("month_period")
        .reset_index(drop=True)
    )
    high, low = overall_mean * (1 + threshold_pct), overall_mean * (1 - threshold_pct)
    monthly["season"] = np.where(
        monthly["mean_required"] >= high, "peak",
        np.where(monthly["mean_required"] <= low, "lean", "shoulder"),
    )
    daily["season"] = daily["month_period"].map(dict(zip(monthly["month_period"], monthly["season"])))

    seasons = []
    for sdef in SEASON_DEFS:
        vals = daily.loc[daily["season"] == sdef["key"], "required_rakes"]
        if vals.empty:
            continue
        seasons.append({
            "key": sdef["key"],
            "label": sdef["label"],
            "months": monthly.loc[monthly["season"] == sdef["key"], "month_period"].tolist(),
            "n_days": int(len(vals)),
            "mean": float(vals.mean()),
            "min": float(vals.min()),
            "p10": float(np.percentile(vals, 10)),
            "p50": float(np.percentile(vals, 50)),
            "p90": float(np.percentile(vals, 90)),
            "peak": float(vals.max()),
        })

    by_key = {s["key"]: s for s in seasons}
    lean, peak = by_key.get("lean"), by_key.get("peak")
    amplitude_pct = ((peak["mean"] / lean["mean"] - 1) * 100) if lean and peak and lean["mean"] else 0.0

    return {
        "seasons": seasons,
        "monthly": monthly.to_dict(orient="records"),
        "overall": {
            "mean": overall_mean,
            "p10": float(np.percentile(daily["required_rakes"], 10)),
            "p50": float(np.percentile(daily["required_rakes"], 50)),
            "p90": float(np.percentile(daily["required_rakes"], 90)),
            "peak": float(daily["required_rakes"].max()),
            "n_days": int(len(daily)),
        },
        "threshold_pct": threshold_pct,
        "amplitude_pct": amplitude_pct,
        # False when the data shows no month far enough from the mean to call a
        # season -- the screens must then not claim seasonality exists.
        "is_seasonal": bool(lean and peak),
    }


def contract_portfolio(
    bundle,
    rake_capacity_t: float = 4000,
    safety_buffer_pct: float = 0.08,
) -> dict:
    """Indicative four-tier contract sizing, derived from the requirement
    distribution -- NOT from the cost optimizer, which is still single-tier.

    Ladder:
      Tier 1 Core     = all-period p10                 (needed on ~90% of days)
      Tier 2 Seasonal = season p50 - core, per season  (floored at 0)
      Tier 3 Options  = observed peak - highest season p50
      Tier 4 Spot     = residual above the observed peak, i.e. growth headroom
    """
    profile = season_profile(bundle, rake_capacity_t, safety_buffer_pct)
    overall = profile["overall"]
    core = overall["p10"]

    top_ups = [
        {
            "season_key": s["key"],
            "season_label": s["label"],
            "months": s["months"],
            "n_days": s["n_days"],
            "top_up": max(s["p50"] - core, 0.0),
            "season_capacity": max(s["p50"], core),
        }
        for s in profile["seasons"]
    ]
    highest_season_p50 = max((s["p50"] for s in profile["seasons"]), default=core)
    options = max(overall["peak"] - highest_season_p50, 0.0)

    tiers = [
        {
            "tier": 1, "key": "core", "name": "Core Take-or-Pay Lease",
            "instrument": "12-month captive/leased rakes (GPWIS / SFTO)",
            "rakes": core,
            "basis": "all-period p10 of daily requirement",
            "rationale": "Capacity needed on ~90% of days, so a take-or-pay commitment is almost never idle -- which is what earns the lowest per-rake rate.",
        },
        {
            "tier": 2, "key": "seasonal", "name": "Seasonal Peak Lease",
            "instrument": "3-6 month seasonal lease block, activated per season",
            "rakes": max((t["top_up"] for t in top_ups), default=0.0),
            "basis": "season p50 minus core, sized per season",
            "rationale": "Lifts capacity to the median day of each season without carrying peak capacity through the lean months.",
        },
        {
            "tier": 3, "key": "options", "name": "Capacity Reservation / Call Option",
            "instrument": "Monthly reservation fee + pre-agreed strike per rake",
            "rakes": options,
            "basis": "observed peak minus the highest season p50",
            "rationale": "Buys the RIGHT to a rake rather than the rake itself -- converting wagon-availability risk into a contractual guarantee at a fraction of the cost of owning the capacity.",
        },
        {
            "tier": 4, "key": "spot", "name": "Residual Spot (FOIS)",
            "instrument": "Uncontracted spot bookings",
            "rakes": 0.0,
            "basis": "anything above the observed peak",
            "rationale": "Genuinely uncertain capacity, held only as headroom for demand beyond anything in the record.",
        },
    ]

    return {
        "tiers": tiers,
        "season_top_ups": top_ups,
        "contracted_capacity": core + max((t["top_up"] for t in top_ups), default=0.0) + options,
        "profile": profile,
        "sizing_basis": (
            "Indicative sizing from the observed requirement distribution. These are "
            "percentile-derived, not cost-optimal: the optimization engine is still "
            "single-tier and does not yet price a tiered contract."
        ),
    }

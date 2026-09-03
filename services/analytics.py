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

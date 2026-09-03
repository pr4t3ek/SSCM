"""Convert coal tonnage into rake (wagon-rake) requirements.

The optimizer works in rakes/day, derived from `Coal Demanded` (not
dispatch, which is already rake-constrained historically and would
understate true requirement) plus a configurable safety buffer.
"""
import math

import pandas as pd

TONNAGE_COLUMN_BY_BASIS = {
    "demand": "coal_demanded_t",
    "dispatch": "coal_dispatched_t",
    "produced": "coal_produced_t",
}


def required_rakes_continuous(tonnes: float, rake_capacity_t: float) -> float:
    return tonnes / rake_capacity_t


def required_rakes_discrete(tonnes: float, rake_capacity_t: float) -> int:
    return math.ceil(tonnes / rake_capacity_t)


def required_rakes_for_tonnes(tonnes, rake_capacity_t, safety_buffer_pct=0.0, discrete=True):
    effective_tonnes = tonnes * (1 + safety_buffer_pct)
    rakes = required_rakes_continuous(effective_tonnes, rake_capacity_t)
    return math.ceil(rakes) if discrete else rakes


def daily_requirement_series(
    dated_df: pd.DataFrame,
    tonnage_basis: str = "demand",
    rake_capacity_t: float = 4000,
    safety_buffer_pct: float = 0.08,
) -> pd.DataFrame:
    """Aggregate shift-level tonnage to a per-day required-rakes series.

    Returns columns: date, total_tonnes, required_rakes (continuous --
    the optimizer works with the continuous figure so its convex
    piecewise-linear cost curve stays exact; discrete rounding is only
    applied for display).
    """
    column = TONNAGE_COLUMN_BY_BASIS[tonnage_basis]
    daily = (
        dated_df.groupby("date", as_index=False)[column]
        .sum()
        .rename(columns={column: "total_tonnes"})
        .sort_values("date")
        .reset_index(drop=True)
    )
    effective = daily["total_tonnes"] * (1 + safety_buffer_pct)
    daily["required_rakes"] = effective / rake_capacity_t
    daily["required_rakes_discrete"] = daily["required_rakes"].apply(math.ceil)
    return daily

"""Load, clean and cache the Lakhanpur shift-wise coal dataset.

The raw workbook is the single source of truth and is read once per process;
`data/lakhanpur_shift_data.csv` is written out as a derived, inspectable
export (per the project's suggested file layout) but is never read back in.

Every consumer (services, routes) should call `get_dataset()` rather than
touching pandas/openpyxl directly, so cleaning/derivation logic lives in
exactly one place.
"""
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

import numpy as np
import pandas as pd

import config

COLUMN_RENAME_MAP = {
    "Mine": "mine",
    "Subsidiary": "subsidiary",
    "Location": "location",
    "Date": "date",
    "Shift Number": "shift_number",
    "Shift Timing": "shift_timing",
    "Coal Produced (Tonnes)": "coal_produced_t",
    "Coal Despatched/Consumed (Tonnes)": "coal_dispatched_t",
    "Coal Demanded (Tonnes)": "coal_demanded_t",
}

SHIFT_ORDER = [1, 2, 3]


@dataclass
class DatasetBundle:
    raw: pd.DataFrame
    clean: pd.DataFrame
    dated: pd.DataFrame
    data_quality: dict
    loaded_at: datetime


def load_raw_dataframe(path: str = config.RAW_XLSX_PATH) -> pd.DataFrame:
    df = pd.read_excel(path)
    return _rename_columns(df)


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_RENAME_MAP)
    missing = set(COLUMN_RENAME_MAP.values()) - set(df.columns)
    if missing:
        raise ValueError(f"Source workbook is missing expected columns: {missing}")
    return df


def _detect_data_quality_issues(df_raw: pd.DataFrame) -> dict:
    """Compute data-quality findings generically from the raw frame.

    Nothing here is hardcoded to a specific date/row -- if the source
    workbook were replaced with a cleaner extract, this would report an
    empty set of issues rather than stale findings.
    """
    missing_date_rows = []
    null_mask = df_raw["date"].isnull()
    for idx in df_raw.index[null_mask]:
        row = df_raw.loc[idx]
        likely_context = None
        prev_idx = idx - 1
        if prev_idx in df_raw.index and pd.notnull(df_raw.loc[prev_idx, "date"]):
            prev = df_raw.loc[prev_idx]
            likely_context = {
                "previous_row_date": prev["date"].strftime("%Y-%m-%d"),
                "previous_row_shift_number": int(prev["shift_number"]),
            }
        missing_date_rows.append({
            "row_index": int(idx),
            "shift_number": int(row["shift_number"]),
            "shift_timing": row["shift_timing"],
            "coal_produced_t": int(row["coal_produced_t"]),
            "coal_dispatched_t": int(row["coal_dispatched_t"]),
            "coal_demanded_t": int(row["coal_demanded_t"]),
            "likely_context": likely_context,
        })

    dated_only = df_raw[~null_mask]
    counts = dated_only.groupby("date")["shift_number"].apply(list)
    incomplete_days = []
    for date, shifts in counts.items():
        present = sorted(int(s) for s in shifts)
        if present != SHIFT_ORDER:
            incomplete_days.append({
                "date": date.strftime("%Y-%m-%d"),
                "shift_count": len(present),
                "present_shifts": present,
                "missing_shift_numbers": [s for s in SHIFT_ORDER if s not in present],
            })

    duplicate_row_count = int(df_raw.duplicated().sum())
    dated_dates = dated_only["date"].dropna()

    return {
        "total_rows": int(len(df_raw)),
        "dated_rows": int(len(dated_only)),
        "missing_date_rows": missing_date_rows,
        "incomplete_days": incomplete_days,
        "duplicate_row_count": duplicate_row_count,
        "unique_dates": int(dated_dates.nunique()),
        "date_range": {
            "start": dated_dates.min().strftime("%Y-%m-%d") if not dated_dates.empty else None,
            "end": dated_dates.max().strftime("%Y-%m-%d") if not dated_dates.empty else None,
        },
        "notes": [
            f"{len(missing_date_rows)} row(s) have a missing Date value.",
            f"{len(incomplete_days)} day(s) have fewer than the expected 3 shifts recorded.",
            f"{duplicate_row_count} fully duplicate row(s) detected." if duplicate_row_count
                else "No fully duplicate rows detected.",
        ],
    }


def _detect_outliers(dated: pd.DataFrame) -> dict:
    """IQR-based outlier flags on shift-level deficit -- purely descriptive,
    rows are never dropped or altered because of this.
    """
    q1, q3 = dated["deficit_t"].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mask = (dated["deficit_t"] < lower) | (dated["deficit_t"] > upper)
    outlier_rows = dated.loc[mask, ["date", "shift_number", "shift_label", "deficit_t"]].copy()
    outlier_rows["date"] = outlier_rows["date"].dt.strftime("%Y-%m-%d")
    return {
        "count": int(mask.sum()),
        "lower_bound": float(lower),
        "upper_bound": float(upper),
        "rows": outlier_rows.to_dict(orient="records"),
    }


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["deficit_t"] = df["coal_demanded_t"] - df["coal_dispatched_t"]
    df["fulfilment_pct"] = np.where(
        df["coal_demanded_t"] > 0,
        df["coal_dispatched_t"] / df["coal_demanded_t"] * 100,
        np.nan,
    )
    df["production_gap_t"] = df["coal_demanded_t"] - df["coal_produced_t"]
    df["is_deficit_positive"] = df["deficit_t"] > 0
    df["date_is_missing"] = df["date"].isnull()
    df["day_of_week"] = df["date"].dt.day_name()
    df["week_start"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")
    df["month_period"] = df["date"].dt.strftime("%Y-%m")
    df["shift_label"] = df["shift_timing"].str.replace(r"\s*\(.*\)", "", regex=True)
    return df


def build_dataset() -> DatasetBundle:
    raw = load_raw_dataframe()
    data_quality = _detect_data_quality_issues(raw)
    clean = _add_derived_columns(raw)
    dated = (
        clean[~clean["date_is_missing"]]
        .sort_values(["date", "shift_number"])
        .reset_index(drop=True)
    )

    export = dated.drop(columns=["date_is_missing"]).copy()
    export["date"] = export["date"].dt.strftime("%Y-%m-%d")
    export.to_csv(config.CLEAN_CSV_PATH, index=False)

    data_quality["outliers"] = _detect_outliers(dated)
    data_quality["notes"].append(
        f"{data_quality['outliers']['count']} shift(s) flagged as deficit outliers (outside 1.5x IQR)."
    )

    return DatasetBundle(
        raw=raw,
        clean=clean,
        dated=dated,
        data_quality=data_quality,
        loaded_at=datetime.now(),
    )


@lru_cache(maxsize=1)
def get_dataset() -> DatasetBundle:
    return build_dataset()

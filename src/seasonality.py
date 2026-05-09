"""
Seasonality module — handles annual cycles, holiday periods, and YoY comparison.

Key idea: don't compare August silence to a non-summer baseline. Compare like-for-like.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


# Spanish calendar / sales-cycle holiday windows where B2B activity drops sharply.
# Augost 1-31 (vacation), Christmas week (Dec 22 - Jan 6).
def is_holiday_period(date: pd.Timestamp) -> bool:
    if date.month == 8:
        return True
    if date.month == 12 and date.day >= 22:
        return True
    if date.month == 1 and date.day <= 6:
        return True
    return False


def seasonal_factors(ventas: pd.DataFrame) -> pd.DataFrame:
    """
    Compute monthly seasonal factor per (bloque_analitico, familia_h) over the
    full history. Factor = (mean monthly volume of this familia in this calendar
    month) / (mean monthly volume of this familia overall).

    A factor < 1 means "this month is below average for this familia" (e.g. August).
    """
    if "bloque_analitico" not in ventas.columns:
        return pd.DataFrame()
    sales = ventas[ventas["unidades"] > 0].copy()
    sales["fecha"] = pd.to_datetime(sales["fecha"])
    sales["year_month"] = sales["fecha"].dt.to_period("M")
    sales["month"] = sales["fecha"].dt.month

    monthly_vol = (sales.groupby(["bloque_analitico", "familia_h", "year_month", "month"])
                       ["valores_h"].sum().reset_index())

    by_month = (monthly_vol.groupby(["bloque_analitico", "familia_h", "month"])
                            ["valores_h"].mean().reset_index()
                            .rename(columns={"valores_h": "mean_month"}))
    overall = (monthly_vol.groupby(["bloque_analitico", "familia_h"])
                          ["valores_h"].mean().reset_index()
                          .rename(columns={"valores_h": "mean_overall"}))
    sf = by_month.merge(overall, on=["bloque_analitico", "familia_h"])
    sf["seasonal_factor"] = (sf["mean_month"] / sf["mean_overall"]).round(3)
    return sf[["bloque_analitico", "familia_h", "month", "seasonal_factor"]]


def yoy_baseline(sales: pd.DataFrame, as_of: pd.Timestamp,
                 window_days: int = 90) -> pd.DataFrame:
    """
    Compute volume and frequency in the same calendar window one year earlier.
    Returns per-(id_cliente, familia_h) DataFrame.
    """
    yoy_end = as_of - pd.DateOffset(years=1)
    yoy_start = yoy_end - pd.Timedelta(days=window_days)
    yoy = sales[(sales["fecha"] > yoy_start) & (sales["fecha"] <= yoy_end)]
    return (yoy.groupby(["id_cliente", "familia_h"])
               .agg(frequency_yoy=("fecha_d", "nunique"),
                    volume_yoy=("valores_h", "sum"))
               .reset_index())


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import load_data
    data = load_data()
    sf = seasonal_factors(data["ventas"])
    print("Seasonal factors by (bloque, familia, month):")
    pivot = sf.pivot_table(index=["bloque_analitico", "familia_h"],
                           columns="month", values="seasonal_factor")
    print(pivot.round(2).to_string())

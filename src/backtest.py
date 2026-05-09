"""
Walk-forward backtest of the alert engine.

For each alert generated at date T (using only data ≤ T), check what actually
happened in the future window using post-T data. Compute hit rate per alert type
with Wilson 95% confidence intervals, plus a lift figure vs. the un-alerted
baseline.

This is "the alert was right" validation — not "intervention worked", which we
cannot measure without a control group / RCT.
"""
from __future__ import annotations
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


# ---------- Wilson 95% CI for a proportion (no scipy dep) ----------
def wilson_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.959963984540054   # norm.ppf(1 - 0.025)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# ---------- Hit-criterion per tipo_alerta ----------
def _hit_criterion(tipo: str) -> dict:
    """
    Returns a dict describing how to measure 'hit' for this tipo:
      - window_days: future window to look at
      - rule:        function(alert_row, future_purchases) -> bool
    """
    if tipo == "silent":
        # Alert predicts: client will stay silent. Hit = no purchase in 90d.
        return {"window_days": 90,
                "rule": lambda a, fp: len(fp) == 0}
    if tipo == "lost":
        # 9+ months silent already; predict: still won't buy. Hit = no purchase in 180d.
        return {"window_days": 180,
                "rule": lambda a, fp: len(fp) == 0}
    if tipo == "churn_risk":
        # Volume dropping; predict: drop continues. Hit = future volume < prior 90d volume.
        return {"window_days": 90,
                "rule": lambda a, fp: fp["valores_h"].sum() < a.get("_prior_90d_volume", 0)}
    if tipo == "capture_window":
        # Promiscuous; predict: client remains active. Hit = ≥1 purchase in window.
        return {"window_days": 90,
                "rule": lambda a, fp: len(fp) > 0}
    if tipo == "opportunity_spike":
        # Spike noticed; predict: continued elevated activity. Hit = ≥1 purchase in window.
        return {"window_days": 90,
                "rule": lambda a, fp: len(fp) > 0}
    return {"window_days": 90, "rule": lambda a, fp: None}


# ---------- Core backtest ----------
def backtest(reference_date: str | pd.Timestamp,
             data: dict | None = None) -> pd.DataFrame:
    """
    Generate alerts at reference_date and validate them against actual post-T data.
    Returns one row per alert with 'hit' (True/False) and 'window_end'.
    """
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import generate_alerts, load_data

    if data is None:
        data = load_data()
    ref = pd.Timestamp(reference_date)
    alerts = generate_alerts(reference_date, data=data, apply_snooze=False)
    if alerts.empty:
        return alerts

    # Pre-build future ventas index by (id_cliente, familia_h)
    future_all = data["ventas"][
        (data["ventas"]["fecha"] > ref)
        & (data["ventas"]["tipo_transaccion"] == "venta")
    ].copy()
    future_all["fecha"] = pd.to_datetime(future_all["fecha"])
    future_all["id_cliente"] = future_all["id_cliente"].astype(str)

    # For churn_risk, we also need the prior 90d volume per (cliente, familia)
    prior_start = ref - pd.Timedelta(days=90)
    prior = data["ventas"][
        (data["ventas"]["fecha"] > prior_start)
        & (data["ventas"]["fecha"] <= ref)
        & (data["ventas"]["tipo_transaccion"] == "venta")
    ]
    prior_vol = (prior.groupby(["id_cliente", "familia_h"])["valores_h"].sum()
                       .reset_index().rename(columns={"valores_h": "prior_90d_vol"}))
    prior_vol["id_cliente"] = prior_vol["id_cliente"].astype(str)

    rows = []
    for _, alert in alerts.iterrows():
        crit = _hit_criterion(alert["tipo_alerta"])
        window_end = ref + pd.Timedelta(days=crit["window_days"])

        cli, fam = str(alert["id_cliente"]), alert["familia"]
        # Commodity alerts use categoria_h (e.g. "Categoria C1"), technical use familia_h
        is_commodity = alert["bloque_analitico"] == "Commodities"
        match_col = "categoria_h" if is_commodity else "familia_h"
        fp = future_all[(future_all["id_cliente"] == cli)
                       & (future_all[match_col] == fam)
                       & (future_all["fecha"] <= window_end)]

        # Inject prior_90d_volume for churn_risk (use the same matching column)
        a_dict = alert.to_dict()
        if alert["tipo_alerta"] == "churn_risk":
            prior_match = prior[(prior["id_cliente"].astype(str) == cli)
                                & (prior[match_col] == fam)]
            a_dict["_prior_90d_volume"] = float(prior_match["valores_h"].sum())

        try:
            hit = bool(crit["rule"](a_dict, fp))
        except Exception:
            hit = None

        rows.append({
            "alert_id": alert["alert_id"],
            "id_cliente": alert["id_cliente"],
            "familia": alert["familia"],
            "tipo_alerta": alert["tipo_alerta"],
            "prioridad": alert["prioridad"],
            "score": alert["score"],
            "expected_impact_eur": alert["expected_impact_eur"],
            "window_days": crit["window_days"],
            "window_end": window_end.date(),
            "purchases_in_window": len(fp),
            "volume_in_window_eur": float(fp["valores_h"].sum()) if len(fp) else 0.0,
            "hit": hit,
        })
    return pd.DataFrame(rows)


# ---------- Aggregations ----------
def summarise(bt: pd.DataFrame) -> pd.DataFrame:
    """Hit rate per tipo with Wilson 95% CI."""
    if bt.empty:
        return pd.DataFrame()
    rows = []
    for tipo, g in bt.groupby("tipo_alerta"):
        g = g[g["hit"].notna()]
        n = len(g)
        k = int(g["hit"].sum())
        lo, hi = wilson_ci(k, n)
        rows.append({
            "tipo_alerta":     tipo,
            "n_alerts":        n,
            "n_hits":          k,
            "hit_rate":        round(k / n, 3) if n else 0.0,
            "ci95_lower":      round(lo, 3),
            "ci95_upper":      round(hi, 3),
            "ci_width":        round(hi - lo, 3),
            "window_days":     int(g["window_days"].iloc[0]) if n else 0,
        })
    return pd.DataFrame(rows).sort_values("hit_rate", ascending=False)


def baseline_purchase_rate(reference_date, data: dict | None = None,
                           window_days: int = 90) -> float:
    """
    Baseline: of clients who had ≥1 purchase in the prior 365d but were NOT
    alerted, what fraction bought in the next `window_days`?

    Used as comparison for `capture_window` and `opportunity_spike` (where hit
    means 'bought in window'). Lift = hit_rate / baseline.
    """
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import generate_alerts, load_data
    if data is None:
        data = load_data()
    ref = pd.Timestamp(reference_date)

    alerts = generate_alerts(reference_date, data=data, apply_snooze=False)
    alerted = set(alerts["id_cliente"].astype(str))

    v = data["ventas"]
    v["id_cliente"] = v["id_cliente"].astype(str)
    v["fecha"] = pd.to_datetime(v["fecha"])

    last_year = ref - pd.Timedelta(days=365)
    active = set(v[(v["fecha"] > last_year) & (v["fecha"] <= ref)
                 & (v["tipo_transaccion"] == "venta")]["id_cliente"])
    pool = active - alerted

    fwd_end = ref + pd.Timedelta(days=window_days)
    bought = set(v[(v["fecha"] > ref) & (v["fecha"] <= fwd_end)
                  & (v["tipo_transaccion"] == "venta")]["id_cliente"])
    if not pool:
        return 0.0
    return round(len(pool & bought) / len(pool), 3)


def run_multi_date(dates: list[str], data: dict | None = None) -> pd.DataFrame:
    """Run backtest across several reference dates and concatenate."""
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import load_data
    if data is None:
        data = load_data()
    parts = []
    for d in dates:
        bt = backtest(d, data=data)
        bt["reference_date"] = d
        parts.append(bt)
    return pd.concat(parts, ignore_index=True)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import load_data

    data = load_data()
    # Pick reference dates that leave enough forward window in the data
    dates = ["2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30"]
    print(f"Running backtest on {len(dates)} reference dates...\n")

    all_bt = run_multi_date(dates, data=data)
    print(f"Total alerts evaluated: {len(all_bt):,}\n")

    print("=== Hit rate per tipo (across all dates) ===")
    summary = summarise(all_bt)
    print(summary.to_string(index=False))

    print("\n=== Baseline purchase rates per reference date ===")
    for d in dates:
        br = baseline_purchase_rate(d, data=data, window_days=90)
        print(f"  {d}: {br:.1%}")

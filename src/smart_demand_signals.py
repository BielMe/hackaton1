"""
Smart Demand Signals — daily-cadence alert generator.

Single entrypoint: `generate_alerts(as_of_date)`.

Layers (per challenge brief):
  1. Data layer       — loads cleaned CSVs
  2. Analytical layer — builds segmentation (commodities + technical)
  3. Activation layer — emits prioritised alerts with traceability
"""
from __future__ import annotations
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "std_data" / "csv"


# -------------------- DATA LAYER --------------------
def load_data() -> dict[str, pd.DataFrame]:
    """Load cleaned CSVs and the lookup mapping."""
    ventas = pd.read_csv(
        CSV_DIR / "Ventas.csv",
        dtype={"id_cliente": str, "id_producto": str, "cliente_no_registrado": str},
        parse_dates=["fecha"],
    )
    ventas["cliente_no_registrado"] = ventas["cliente_no_registrado"].str.strip().eq("True")
    return {
        "ventas": ventas,
        "potencial": pd.read_csv(CSV_DIR / "Potencial.csv", dtype={"id_cliente": str}),
        "clientes": pd.read_csv(CSV_DIR / "Clientes.csv",
                                dtype={"id_cliente": str, "codigo_postal": str}),
        "mapping": pd.read_csv(CSV_DIR / "Mapping_familia.csv"),
        "campanas": pd.read_csv(CSV_DIR / "Campañas.csv",
                                parse_dates=["fecha_inicio", "fecha_fin"]),
    }


def in_campaign_window(date: pd.Timestamp, campanas: pd.DataFrame,
                       buffer_days: int = 14) -> tuple[bool, str | None]:
    """Return (True, name) if date is within ±buffer_days of any campaign window."""
    for _, c in campanas.iterrows():
        start = pd.Timestamp(c["fecha_inicio"]) - pd.Timedelta(days=buffer_days)
        end = pd.Timestamp(c["fecha_fin"]) + pd.Timedelta(days=buffer_days)
        if start <= date <= end:
            return True, c["campana"]
    return False, None


def post_campaign_grace_keys(ventas: pd.DataFrame, campanas: pd.DataFrame,
                             as_of: pd.Timestamp,
                             heavy_multiplier: float = 2.0,
                             window_buffer_days: int = 14) -> set:
    """
    Identify (id_cliente, familia_h) pairs that are in a post-campaign grace
    period — i.e. they bought significantly above their normal pace during a
    recent campaign window, so silence is expected (warehouse is full).

    Returns a set of (id_cliente, familia_h) tuples to be suppressed.
    """
    sales = ventas[(ventas["unidades"] > 0)
                   & ventas["familia_h"].notna()].copy()
    sales["fecha"] = pd.to_datetime(sales["fecha"])
    if sales.empty or campanas.empty:
        return set()

    # Average monthly burn per (cliente, familia_h) over full history
    sales["ym"] = sales["fecha"].dt.to_period("M")
    monthly = (sales.groupby(["id_cliente", "familia_h", "ym"])
                    ["valores_h"].sum().reset_index())
    burn = (monthly.groupby(["id_cliente", "familia_h"])
                    ["valores_h"].mean().reset_index()
                    .rename(columns={"valores_h": "monthly_avg"}))

    # For each campaign, sum what each (cliente, familia_h) bought in the window
    grace_keys: set = set()
    for _, c in campanas.iterrows():
        start = pd.Timestamp(c["fecha_inicio"]) - pd.Timedelta(days=window_buffer_days)
        end = pd.Timestamp(c["fecha_fin"]) + pd.Timedelta(days=window_buffer_days)
        if end > as_of:
            continue  # future campaign
        window_sales = sales[(sales["fecha"] >= start) & (sales["fecha"] <= end)]
        if window_sales.empty:
            continue
        agg = (window_sales.groupby(["id_cliente", "familia_h"])
                          ["valores_h"].sum().reset_index()
                          .rename(columns={"valores_h": "vol_in_window"}))
        agg = agg.merge(burn, on=["id_cliente", "familia_h"], how="left")
        agg["grace_months"] = agg["vol_in_window"] / agg["monthly_avg"].clip(lower=1e-6)
        # Only "heavy" purchases (>= heavy_multiplier × monthly avg) get grace
        heavy = agg[agg["grace_months"] >= heavy_multiplier].copy()
        # Grace ends at end + grace_months (relative to end of campaign window)
        for _, r in heavy.iterrows():
            grace_end = end + pd.Timedelta(days=int(r["grace_months"] * 30))
            if as_of <= grace_end:
                grace_keys.add((r["id_cliente"], r["familia_h"]))
    return grace_keys


def filter_commercial_activity(ventas: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Restrict to registered clients, real commercial transactions, on or before as_of."""
    return ventas[
        (~ventas["cliente_no_registrado"])
        & (ventas["tipo_transaccion"].isin(["venta", "devolucion"]))
        & (ventas["fecha"] <= as_of)
    ].copy()


# -------------------- CLIENT PROFILES --------------------
def build_client_profiles(v: pd.DataFrame, potencial: pd.DataFrame,
                           as_of: pd.Timestamp) -> pd.DataFrame:
    """Per-client profile aggregating cycle / recurrence / health metrics.

    Used by the dashboard's Client view. Critically:
    - share_of_potential uses TRAILING 12 MONTHS (not lifetime) so it never goes >100%
    - cycle_progress = recency / mean_interpurchase_days (>1 means overdue)
    """
    if len(v) == 0:
        return pd.DataFrame()
    cs = (v.groupby("id_cliente")
            .agg(total_purchases=("fecha", "nunique"),
                 total_units=("unidades", "sum"),
                 lifetime_eur=("valores_h", "sum"),
                 first_purchase=("fecha", "min"),
                 last_purchase=("fecha", "max"),
                 n_transactions=("num_factura", "nunique"))
            .reset_index())
    cs["recency_days"]  = (as_of - cs["last_purchase"]).dt.days
    cs["lifespan_days"] = (cs["last_purchase"] - cs["first_purchase"]).dt.days

    # Mean interpurchase / cyclicity (need ≥3 purchases = ≥2 gaps)
    sorted_v = (v[["id_cliente", "fecha"]].drop_duplicates()
                  .sort_values(["id_cliente", "fecha"]))
    sorted_v["gap"] = sorted_v.groupby("id_cliente")["fecha"].diff().dt.days
    gap_stats = (sorted_v.dropna(subset=["gap"])
                          .groupby("id_cliente")["gap"]
                          .agg(["mean", "std", "count"])
                          .reset_index())
    gap_stats.columns = ["id_cliente", "mean_interpurchase_days", "cycle_std", "gap_count"]
    gap_stats = gap_stats[gap_stats["gap_count"] >= 2]
    gap_stats["cyclicity_score"] = (
        1 - gap_stats["cycle_std"] / gap_stats["mean_interpurchase_days"].clip(lower=1)
    ).clip(0, 1)
    cs = cs.merge(
        gap_stats[["id_cliente", "mean_interpurchase_days", "cycle_std", "cyclicity_score"]],
        on="id_cliente", how="left")

    # Trailing 12m volume — for the correct share_of_potential
    d365 = as_of - pd.Timedelta(days=365)
    last_year = (v[v["fecha"] > d365].groupby("id_cliente")["valores_h"].sum()
                                       .reset_index().rename(columns={"valores_h": "eur_last_12m"}))
    cs = cs.merge(last_year, on="id_cliente", how="left")
    cs["eur_last_12m"] = cs["eur_last_12m"].fillna(0)

    # Recent (6m) vs prior 6m for trend
    d180 = as_of - pd.Timedelta(days=180)
    d360 = as_of - pd.Timedelta(days=360)
    rv = (v[v["fecha"] > d180].groupby("id_cliente")["valores_h"].sum()
            .reset_index().rename(columns={"valores_h": "eur_recent_6m"}))
    bv = (v[(v["fecha"] > d360) & (v["fecha"] <= d180)].groupby("id_cliente")["valores_h"].sum()
            .reset_index().rename(columns={"valores_h": "eur_baseline_6m"}))
    cs = cs.merge(rv, on="id_cliente", how="left").merge(bv, on="id_cliente", how="left")
    cs["eur_recent_6m"]   = cs["eur_recent_6m"].fillna(0)
    cs["eur_baseline_6m"] = cs["eur_baseline_6m"].fillna(0)
    cs["potential_trend"] = np.where(
        cs["eur_baseline_6m"] > 0,
        (cs["eur_recent_6m"] - cs["eur_baseline_6m"]) / cs["eur_baseline_6m"],
        np.where(cs["eur_recent_6m"] > 0, 1.0, 0.0))

    # Potential — sum across categorías
    pt = (potencial.groupby("id_cliente")["potencial_h"].sum().reset_index()
                    .rename(columns={"potencial_h": "potencial_total"}))
    cs = cs.merge(pt, on="id_cliente", how="left")
    cs["potencial_total"] = cs["potencial_total"].fillna(0)
    # Correct share — TRAILING 12 MONTHS (annual) divided by annual potential
    cs["share_of_potential"] = np.where(
        cs["potencial_total"] > 0,
        cs["eur_last_12m"] / cs["potencial_total"],
        np.nan)

    # Cycle progress — how far through the expected cycle
    cs["cycle_progress"] = np.where(
        cs["mean_interpurchase_days"].notna() & (cs["mean_interpurchase_days"] > 0),
        cs["recency_days"] / cs["mean_interpurchase_days"], np.nan)
    cs["next_expected_purchase"] = pd.NaT
    has_cycle = cs["mean_interpurchase_days"].notna()
    cs.loc[has_cycle, "next_expected_purchase"] = (
        cs.loc[has_cycle, "last_purchase"]
        + pd.to_timedelta(cs.loc[has_cycle, "mean_interpurchase_days"], unit="D"))
    cs["days_until_next_purchase"] = (cs["next_expected_purchase"] - as_of).dt.days
    return cs


# -------------------- ANALYTICAL LAYER --------------------
def commodity_segments(v: pd.DataFrame, potencial: pd.DataFrame,
                       as_of: pd.Timestamp) -> pd.DataFrame:
    """Per (cliente × categoria_h) for commodities. Share-of-potential rule."""
    cur_start = as_of - pd.Timedelta(days=365)
    base_start = as_of - pd.Timedelta(days=730)
    com = v[v["bloque_analitico"] == "Commodities"].copy()
    com["period"] = pd.cut(
        com["fecha"],
        bins=[pd.Timestamp.min, base_start, cur_start, pd.Timestamp.max],
        labels=["older", "baseline", "current"],
    )

    g = (com.groupby(["id_cliente", "categoria_h", "bloque_analitico", "period"], observed=True)
            .agg(volume_eur=("valores_h", "sum"), frequency=("fecha", "nunique"))
            .reset_index())
    agg = (g[g["period"].isin(["current", "baseline"])]
           .pivot_table(index=["id_cliente", "categoria_h", "bloque_analitico"],
                        columns="period", values=["volume_eur", "frequency"],
                        fill_value=0, observed=True)
           .reset_index())
    agg.columns = ["_".join(map(str, c)).rstrip("_") if isinstance(c, tuple) and c[1]
                   else (c[0] if isinstance(c, tuple) else c) for c in agg.columns]

    # Guarantee both period columns exist even when one window is empty (early dates)
    for col in ["volume_eur_current", "volume_eur_baseline",
                "frequency_current", "frequency_baseline"]:
        if col not in agg.columns:
            agg[col] = 0

    rec = (com.groupby(["id_cliente", "categoria_h"])["fecha"].max()
              .reset_index().rename(columns={"fecha": "last_purchase"}))
    rec["recency_days"] = (as_of - rec["last_purchase"]).dt.days
    agg = agg.merge(rec[["id_cliente", "categoria_h", "recency_days"]],
                    on=["id_cliente", "categoria_h"], how="left")

    # Mean interpurchase days per (cliente, categoria) — used for dynamic windows + cyclic filter
    sorted_com = com[["id_cliente", "categoria_h", "fecha"]].drop_duplicates().sort_values(
        ["id_cliente", "categoria_h", "fecha"])
    sorted_com["gap"] = sorted_com.groupby(["id_cliente", "categoria_h"])["fecha"].diff().dt.days
    mipd = (sorted_com.dropna(subset=["gap"])
                       .groupby(["id_cliente", "categoria_h"])["gap"].mean()
                       .reset_index().rename(columns={"gap": "mean_interpurchase_days"}))
    agg = agg.merge(mipd, on=["id_cliente", "categoria_h"], how="left")
    # Lifespan (first → last purchase) for safe annual projection
    span = (com.groupby(["id_cliente", "categoria_h"])["fecha"]
                .agg(first_purchase="min", last_purchase="max").reset_index())
    span["lifespan_days"] = (span["last_purchase"] - span["first_purchase"]).dt.days
    agg = agg.merge(span[["id_cliente", "categoria_h", "lifespan_days"]],
                    on=["id_cliente", "categoria_h"], how="left")

    pot = potencial.groupby(["id_cliente", "categoria_h"])["potencial_h"].sum().reset_index()
    agg = agg.merge(pot, on=["id_cliente", "categoria_h"], how="left").fillna({"potencial_h": 0})
    agg["share_of_potential"] = agg.apply(
        lambda r: (r["volume_eur_current"] / r["potencial_h"]) if r["potencial_h"] > 0 else None,
        axis=1)

    def label(r):
        pot, curr, base = r["potencial_h"], r["volume_eur_current"], r["volume_eur_baseline"]
        rec = r["recency_days"] if pd.notna(r["recency_days"]) else 9999
        s = r["share_of_potential"]
        # >9 months silent AND no current activity = likely lost (low priority recovery)
        if rec > 270 and curr <= 0: return "lost"
        if base > 0 and curr <= 0: return "churn_risk_silent"
        if base > 0 and curr < 0.5 * base: return "churn_risk_dropping"
        if pot is None or pd.isna(pot) or pot == 0: return "unknown_potential"
        if s >= 0.30: return "loyal"
        if s < 0.05: return "marginal"
        return "promiscuous"

    agg["segment"] = agg.apply(label, axis=1)

    # Loyalty tier — sub-labels within the 5-30% promiscuous band for nuance
    def loyalty_tier(r):
        s = r["share_of_potential"]
        if s is None or pd.isna(s):
            return "unknown"
        if s >= 0.30: return "loyal"
        if s >= 0.20: return "near_loyal"
        if s >= 0.10: return "moderate"
        if s >= 0.05: return "weakly_engaged"
        return "marginal"
    agg["loyalty_tier"] = agg.apply(loyalty_tier, axis=1)

    # Trend — current period vs baseline
    def trend(r):
        base, curr = r["volume_eur_baseline"], r["volume_eur_current"]
        if base <= 0:
            return "new" if curr > 0 else "inactive"
        ratio = curr / base
        if ratio >= 1.20: return "improving"
        if ratio <= 0.80: return "declining"
        return "stable"
    agg["trend"] = agg.apply(trend, axis=1)

    return agg


def technical_patterns(v: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Per (cliente × familia_h) for technical products. Individual-baseline rule
    with YoY comparison to neutralise seasonality."""
    from seasonality import yoy_baseline, is_holiday_period
    d90 = as_of - pd.Timedelta(days=90)
    d365 = as_of - pd.Timedelta(days=365)
    tech = v[v["bloque_analitico"] == "Productos Técnicos"].copy()
    sales = tech[tech["unidades"] > 0].copy()
    sales["fecha_d"] = sales["fecha"].dt.normalize()

    lt = (sales.groupby(["id_cliente", "familia_h"])
                .agg(purchase_days_total=("fecha_d", "nunique"),
                     first_purchase=("fecha_d", "min"),
                     last_purchase=("fecha_d", "max"),
                     lifetime_volume=("valores_h", "sum"))
                .reset_index())
    lt["lifespan_days"] = (lt["last_purchase"] - lt["first_purchase"]).dt.days
    lt["recency_days"] = (as_of - lt["last_purchase"]).dt.days

    def mipd(s):
        d = s.drop_duplicates().sort_values()
        return None if len(d) < 2 else d.diff().dt.days.dropna().mean()

    m = (sales.groupby(["id_cliente", "familia_h"])["fecha_d"]
              .apply(mipd).reset_index(name="mean_interpurchase_days"))
    lt = lt.merge(m, on=["id_cliente", "familia_h"], how="left")

    rec = sales[sales["fecha"] > d90]
    base = sales[(sales["fecha"] > d365) & (sales["fecha"] <= d90)]
    wr = (rec.groupby(["id_cliente", "familia_h"])
              .agg(frequency_recent=("fecha_d", "nunique"),
                   volume_recent=("valores_h", "sum"))
              .reset_index())
    wb = (base.groupby(["id_cliente", "familia_h"])
               .agg(frequency_baseline=("fecha_d", "nunique"),
                    volume_baseline=("valores_h", "sum"))
               .reset_index())
    yoy = yoy_baseline(sales, as_of, window_days=90)
    df = (lt.merge(wr, on=["id_cliente", "familia_h"], how="left")
            .merge(wb, on=["id_cliente", "familia_h"], how="left")
            .merge(yoy, on=["id_cliente", "familia_h"], how="left")
            .fillna({"frequency_recent": 0, "volume_recent": 0,
                     "frequency_baseline": 0, "volume_baseline": 0,
                     "frequency_yoy": 0, "volume_yoy": 0}))

    # Default expected = 90/275 of trailing baseline; if YoY data exists, prefer that
    # (same-calendar window last year) — neutralises seasonality, esp. August.
    df["expected_freq_recent"] = df["frequency_baseline"] * (90 / 275)
    df["expected_vol_recent"]  = df["volume_baseline"] * (90 / 275)
    yoy_mask = df["volume_yoy"] > 0
    df.loc[yoy_mask, "expected_freq_recent"] = df.loc[yoy_mask, "frequency_yoy"]
    df.loc[yoy_mask, "expected_vol_recent"]  = df.loc[yoy_mask, "volume_yoy"]
    df["baseline_source"] = yoy_mask.map({True: "yoy", False: "trailing"})

    df["freq_drop_ratio"] = df.apply(
        lambda r: r["frequency_recent"] / r["expected_freq_recent"]
        if r["expected_freq_recent"] > 0 else None, axis=1)
    df["vol_drop_ratio"] = df.apply(
        lambda r: r["volume_recent"] / r["expected_vol_recent"]
        if r["expected_vol_recent"] > 0 else None, axis=1)

    df["signal_absent"]       = df["frequency_recent"] == 0
    df["signal_drop_freq"]    = df["expected_freq_recent"].gt(0) & (df["freq_drop_ratio"].fillna(1) < 0.5)
    df["signal_drop_volume"]  = df["expected_vol_recent"].gt(0) & (df["vol_drop_ratio"].fillna(1) < 0.5)
    df["signal_anomaly_high"] = df["expected_vol_recent"].gt(0) & (df["vol_drop_ratio"].fillna(0) > 2.0)

    # Holiday-aware suppression: if as_of is in a holiday window AND the YoY drop
    # isn't severe (>0.5×), don't fire absent/drop signals — likely seasonal pause.
    holiday = is_holiday_period(as_of)
    if holiday:
        seasonal_mask = (df["volume_yoy"] > 0) & (df["vol_drop_ratio"].fillna(1) >= 0.5)
        df.loc[seasonal_mask, "signal_absent"]      = False
        df.loc[seasonal_mask, "signal_drop_freq"]   = False
        df.loc[seasonal_mask, "signal_drop_volume"] = False
    df["holiday_period"] = holiday

    def pattern(r):
        if r["purchase_days_total"] < 3: return "insufficient_history"
        # 9+ months silent -> a candidate for `lost` (gated by _is_cyclic_client downstream)
        if pd.notna(r["recency_days"]) and r["recency_days"] >= 270:
            return "lost"
        sys_pat = pd.notna(r["mean_interpurchase_days"]) and r["mean_interpurchase_days"] <= 90
        if sys_pat:
            if r["signal_absent"]: return "systematic_silent"
            if r["signal_drop_freq"] or r["signal_drop_volume"]: return "systematic_deterioration"
            if r["signal_anomaly_high"]: return "systematic_spike"
            return "systematic_active"
        if r["signal_absent"] and r["frequency_baseline"] > 0: return "occasional_silent"
        if r["signal_absent"]: return "occasional_dormant"
        if r["signal_anomaly_high"]: return "occasional_spike"
        return "occasional_active"

    df["pattern"] = df.apply(pattern, axis=1)

    # Trend based on volume drop ratio
    def trend(r):
        if pd.isna(r["vol_drop_ratio"]):
            return "new" if r["volume_recent"] > 0 else "inactive"
        if r["vol_drop_ratio"] >= 1.20: return "improving"
        if r["vol_drop_ratio"] <= 0.80: return "declining"
        return "stable"
    df["trend"] = df.apply(trend, axis=1)
    return df


# -------------------- ACTIVATION LAYER --------------------
# Tunable thresholds for the cyclic-client filter on `lost` alerts.
MIN_PURCHASES_FOR_LOST = 3      # need at least this many distinct purchase days
MIN_VOLUME_FOR_LOST    = 200    # and at least €200 lifetime to be worth pursuing
MAX_CYCLE_FOR_LOST     = 365    # if their cycle is >1y they are not really cyclic
MIN_LIFESPAN_FOR_ANNUAL = 90    # don't extrapolate annual rate from <90 days


def _safe_annual(lifetime_volume, lifespan_days):
    """Project annual volume only if there's enough history. Otherwise return raw total."""
    ls = lifespan_days if pd.notna(lifespan_days) and lifespan_days > 0 else 0
    if ls >= MIN_LIFESPAN_FOR_ANNUAL:
        return (lifetime_volume / ls) * 365
    return lifetime_volume


def _is_cyclic_client(r, block="commodity"):
    """Did this client buy enough times to be worth a `lost` recovery alert?"""
    if block == "commodity":
        freq = (r.get("frequency_current", 0) or 0) + (r.get("frequency_baseline", 0) or 0)
        vol  = (r.get("volume_eur_current", 0) or 0) + (r.get("volume_eur_baseline", 0) or 0)
    else:
        freq = r.get("purchase_days_total", 0) or 0
        vol  = r.get("lifetime_volume", 0) or 0
    if freq < MIN_PURCHASES_FOR_LOST or vol < MIN_VOLUME_FOR_LOST:
        return False
    mipd = r.get("mean_interpurchase_days")
    if pd.notna(mipd) and mipd > MAX_CYCLE_FOR_LOST:
        # Allow if annualised volume is still meaningful
        ls = r.get("lifespan_days", 365) or 365
        return _safe_annual(vol, ls) >= 500
    return True


def _dynamic_contact_window(r, default_win):
    """Adapt contact window to the client's individual purchase cycle."""
    mipd = r.get("mean_interpurchase_days")
    if mipd is None or pd.isna(mipd):
        return default_win
    rec = r.get("recency_days", 0) or 0
    days_until_expected = mipd - rec
    if days_until_expected <= 0:
        return max(2, default_win // 4)        # already overdue — act fast
    return min(int(days_until_expected), default_win)


def _commodity_alert(r):
    seg = r["segment"]
    if seg == "lost":
        # Only fire `lost` for clients who really were cyclic — otherwise no alert
        if not _is_cyclic_client(r, "commodity"):
            return None
        rec = r["recency_days"] if pd.notna(r["recency_days"]) else 365
        impact = max(0.0, r["volume_eur_baseline"])    # full baseline — they were valuable
        urg, conv = 0.30, 0.15                          # low odds, low urgency
        tipo = "lost"
        motivo = (f"Lost client: {int(rec)}d without buying (>270d). "
                  f"Used to buy ~€{impact:,.0f}/yr in baseline.")
        prio = "High" if impact > 1000 else "Medium"
        canal, win = "delegado", _dynamic_contact_window(r, 7)
    elif seg == "promiscuous":
        # Realistic capture: 30-50% growth on what they already buy, NOT full gap-to-potential
        share = r["share_of_potential"] or 0
        curr = max(0.0, r["volume_eur_current"])
        impact = max(0.0, curr * 0.5) if share < 0.3 else max(0.0, curr * 0.3)
        urg, tipo = 0.7, "capture_window"
        conv = min(1.0, max(0.10, share / 0.30))
        motivo = (f"Promiscuous client: capturing {share:.0%} of estimated potential. "
                  f"Realistic growth margin: ~€{impact:,.0f}.")
        prio = "High" if impact > 1500 else ("Medium" if impact > 500 else "Low")
        canal = "delegado" if prio == "High" else "televenta"
        win = _dynamic_contact_window(r, 7 if prio == "High" else (30 if prio == "Medium" else 90))
        if prio == "Low":
            canal = "marketing_automation"
            win = max(win, 30)
    elif seg == "churn_risk_silent":
        impact = max(0.0, r["volume_eur_baseline"])
        rec = r["recency_days"] if pd.notna(r["recency_days"]) else 365
        urg = max(0.2, 1.0 - max(0, rec - 180) / 365)
        conv = max(0.10, 1.0 - max(0, rec - 90) / 365)
        tipo = "silent"
        motivo = (f"Loyal client gone silent: ~€{impact:,.0f}/yr in baseline; "
                  f"no purchase for {int(rec)}d.")
        prio = "High" if (impact > 1000 and rec < 365) else "Medium"
        canal = "delegado" if prio == "High" else "televenta"
        win = _dynamic_contact_window(r, 7 if prio == "High" else 30)
    else:  # churn_risk_dropping
        impact = max(0.0, r["volume_eur_baseline"] - r["volume_eur_current"])
        urg, tipo = 0.9, "churn_risk"
        conv = 0.65
        drop_pct = (1 - r["volume_eur_current"] / max(1, r["volume_eur_baseline"])) * 100
        motivo = (f"Sustained drop: €{r['volume_eur_baseline']:,.0f} → "
                  f"€{r['volume_eur_current']:,.0f} (-{drop_pct:.0f}%).")
        prio = "High" if impact > 1500 else "Medium"
        canal = "delegado" if prio == "High" else "televenta"
        win = _dynamic_contact_window(r, 7 if prio == "High" else 30)
    return tipo, motivo, prio, impact, urg, canal, win, conv


def _technical_alert(r):
    pat = r["pattern"]
    if pat == "systematic_deterioration":
        impact = max(0.0, r["expected_vol_recent"] - r["volume_recent"]) * 4
        urg, tipo = 0.95, "churn_risk"
        conv = 0.55
        motivo = (f"Systematic client deteriorating: €{r['volume_recent']:,.0f} "
                  f"vs expected €{r['expected_vol_recent']:,.0f}.")
        prio = "High" if impact > 2000 else "Medium"
        canal = "delegado"
        win = _dynamic_contact_window(r, 7)
    elif pat == "systematic_silent":
        annual = _safe_annual(r["lifetime_volume"], r.get("lifespan_days"))
        impact = max(0.0, annual)
        rec = r["recency_days"]
        urg = max(0.2, 1.0 - max(0, rec - 180) / 365)
        conv = max(0.10, 1.0 - max(0, rec - 90) / 365)
        tipo = "silent"
        motivo = (f"Systematic client gone silent: ~€{annual:,.0f}/yr historic, "
                  f"no activity for {int(rec)}d.")
        prio = "High" if (impact > 5000 and rec < 365) else "Medium"
        canal = "delegado" if prio == "High" else "televenta"
        win = _dynamic_contact_window(r, 7 if prio == "High" else 30)
    elif pat == "occasional_silent":
        impact = max(0.0, r["volume_baseline"])
        urg, tipo = 0.5, "silent"
        conv = 0.30
        motivo = f"Occasional client with no recent purchase: €{impact:,.0f} in baseline."
        prio = "Medium" if impact > 500 else "Low"
        canal = "televenta" if prio == "Medium" else "marketing_automation"
        win = 30 if prio == "Medium" else 90
    elif pat == "lost":
        # Technical lost — gate by cyclic-client filter
        if not _is_cyclic_client(r, "technical"):
            return None
        annual = _safe_annual(r["lifetime_volume"], r.get("lifespan_days"))
        impact = max(0.0, annual)
        urg, conv = 0.30, 0.15
        tipo = "lost"
        rec = r["recency_days"]
        motivo = (f"Lost client (technical): {int(rec)}d without buying. "
                  f"Historic volume: ~€{impact:,.0f}/yr.")
        prio = "High" if impact > 2000 else "Medium"
        canal, win = "delegado", _dynamic_contact_window(r, 7)
    else:  # spike
        impact = max(0.0, r["volume_recent"] - r["expected_vol_recent"])
        urg, tipo = 0.4, "opportunity_spike"
        conv = 0.50
        motivo = (f"Anomalous spike: €{r['volume_recent']:,.0f} vs expected "
                  f"€{r['expected_vol_recent']:,.0f} — investigate opportunity.")
        prio = "Medium" if impact > 1000 else "Low"
        canal = "televenta" if prio == "Medium" else "marketing_automation"
        win = 30
    return tipo, motivo, prio, impact, urg, canal, win, conv


def build_alerts(comm_seg: pd.DataFrame, tech_pat: pd.DataFrame,
                 clientes: pd.DataFrame, mapping: pd.DataFrame,
                 as_of: pd.Timestamp) -> pd.DataFrame:
    fam_map = dict(zip(mapping["categoria_h"], mapping["familia_comercial"]))
    rows = []

    for _, r in comm_seg[comm_seg["segment"].isin(
            ["promiscuous", "churn_risk_silent", "churn_risk_dropping", "lost"])].iterrows():
        result = _commodity_alert(r)
        if result is None:
            continue
        tipo, motivo, prio, impact, urg, canal, win, conv = result
        rows.append({
            "id_cliente": r["id_cliente"],
            "bloque_analitico": "Commodities",
            "categoria_h": r["categoria_h"],
            "familia": r["categoria_h"],
            "familia_comercial": fam_map.get(r["categoria_h"]),
            "segment_or_pattern": r["segment"],
            "loyalty_tier": r.get("loyalty_tier", ""),
            "trend": r.get("trend", ""),
            "tipo_alerta": tipo, "motivo": motivo, "prioridad": prio,
            "expected_impact_eur": impact, "urgency_factor": urg,
            "conversion_probability": conv,
            "canal_recomendado": canal, "contact_window_days": win,
            "trace_features": json.dumps({
                "segment": r["segment"],
                "loyalty_tier": r.get("loyalty_tier", ""),
                "trend": r.get("trend", ""),
                "share_of_potential": float(r["share_of_potential"]) if pd.notna(r["share_of_potential"]) else None,
                "potencial_h": float(r["potencial_h"]),
                "volume_eur_current": float(r["volume_eur_current"]),
                "volume_eur_baseline": float(r["volume_eur_baseline"]),
                "recency_days": float(r["recency_days"]) if pd.notna(r["recency_days"]) else None,
                "conversion_probability": conv,
            }),
        })

    for _, r in tech_pat[tech_pat["pattern"].isin([
            "systematic_deterioration", "systematic_silent", "occasional_silent",
            "systematic_spike", "occasional_spike", "lost"])].iterrows():
        result = _technical_alert(r)
        if result is None:
            continue
        tipo, motivo, prio, impact, urg, canal, win, conv = result
        rows.append({
            "id_cliente": r["id_cliente"],
            "bloque_analitico": "Productos Técnicos",
            "categoria_h": "Categoria T1",
            "familia": r["familia_h"],
            "familia_comercial": "Biomateriales (técnicos)",
            "segment_or_pattern": r["pattern"],
            "loyalty_tier": "",
            "trend": r.get("trend", ""),
            "tipo_alerta": tipo, "motivo": motivo, "prioridad": prio,
            "expected_impact_eur": impact, "urgency_factor": urg,
            "conversion_probability": conv,
            "canal_recomendado": canal, "contact_window_days": win,
            "trace_features": json.dumps({
                "pattern": r["pattern"],
                "trend": r.get("trend", ""),
                "recency_days": float(r["recency_days"]) if pd.notna(r["recency_days"]) else None,
                "frequency_recent": int(r["frequency_recent"]),
                "frequency_baseline": int(r["frequency_baseline"]),
                "volume_recent": float(r["volume_recent"]),
                "expected_vol_recent": float(r["expected_vol_recent"]),
                "mean_interpurchase_days": float(r["mean_interpurchase_days"]) if pd.notna(r["mean_interpurchase_days"]) else None,
                "lifetime_volume": float(r["lifetime_volume"]),
                "conversion_probability": conv,
            }),
        })

    a = pd.DataFrame(rows)
    if a.empty:
        return a
    # score = impact × urgency × conversion_probability
    # (the brief lists all four prioritisation signals; client_potential_value
    #  is implicit in expected_impact_eur, time_urgency in urgency_factor)
    a["score"] = a["expected_impact_eur"] * a["urgency_factor"] * a["conversion_probability"]
    a["fecha_alerta"] = as_of.date()
    a = a.merge(clientes[["id_cliente", "provincia"]], on="id_cliente", how="left")
    a = a.sort_values("score", ascending=False).reset_index(drop=True)
    a["alert_id"] = [f"ALT-{as_of.strftime('%Y%m%d')}-{i+1:06d}" for i in range(len(a))]
    return a[[
        "alert_id", "fecha_alerta", "id_cliente", "provincia",
        "bloque_analitico", "categoria_h", "familia", "familia_comercial",
        "tipo_alerta", "motivo", "segment_or_pattern", "loyalty_tier", "trend",
        "prioridad", "score", "expected_impact_eur", "urgency_factor",
        "conversion_probability",
        "canal_recomendado", "contact_window_days", "trace_features",
    ]]


# -------------------- SNOOZE / DEDUP --------------------
def snooze_recently_actioned(alerts: pd.DataFrame, as_of: pd.Timestamp,
                              snooze_days: int = 30) -> pd.DataFrame:
    """
    Suppress alerts whose (id_cliente, familia, tipo_alerta) was acted on
    within the last `snooze_days` and produced a terminal outcome
    (won / lost / false_positive).

    A `pending` or `no_contact` outcome is NOT terminal — those keep firing.
    """
    outcomes_path = ROOT / "analysis" / "alert_outcomes.csv"
    alerts_csv    = ROOT / "analysis" / "alerts.csv"
    if not outcomes_path.exists() or not alerts_csv.exists():
        return alerts
    o = pd.read_csv(outcomes_path, parse_dates=["recorded_at"])
    if o.empty:
        return alerts
    a_hist = pd.read_csv(alerts_csv,
                         dtype={"id_cliente": str},
                         usecols=["alert_id", "id_cliente", "familia", "tipo_alerta"])
    o = o.merge(a_hist, on="alert_id", how="left")
    cutoff = as_of - pd.Timedelta(days=snooze_days)
    snoozed = o[(o["outcome_status"].isin(["won", "lost", "false_positive"]))
                & (o["recorded_at"] >= cutoff)][["id_cliente", "familia", "tipo_alerta"]]
    if snoozed.empty:
        return alerts
    snoozed_keys = set(zip(snoozed["id_cliente"], snoozed["familia"], snoozed["tipo_alerta"]))
    keep_mask = ~alerts.apply(
        lambda r: (r["id_cliente"], r["familia"], r["tipo_alerta"]) in snoozed_keys, axis=1)
    return alerts[keep_mask].reset_index(drop=True)


# -------------------- ENTRY POINT --------------------
def generate_alerts(as_of_date, data: dict | None = None,
                    apply_snooze: bool = True, snooze_days: int = 30) -> pd.DataFrame:
    """
    Generate the daily alert table for a given as-of date.

    Parameters
    ----------
    as_of_date : str | pd.Timestamp
        Reference date. Only data on/before this date is used.
    data : dict, optional
        Pre-loaded dict from `load_data()`. If None, will load fresh.
    apply_snooze : bool, default True
        If True, suppress alerts whose (cliente × familia × tipo) had a
        terminal outcome within the last `snooze_days`.
    snooze_days : int, default 30
        Snooze window size.

    Returns
    -------
    pd.DataFrame
        Sorted alert table (highest score first).
    """
    as_of = pd.Timestamp(as_of_date)
    if data is None:
        data = load_data()
    v = filter_commercial_activity(data["ventas"], as_of)
    cs = commodity_segments(v, data["potencial"], as_of)
    tp = technical_patterns(v, as_of)
    alerts = build_alerts(cs, tp, data["clientes"], data["mapping"], as_of)
    if apply_snooze and not alerts.empty:
        alerts = snooze_recently_actioned(alerts, as_of, snooze_days)
    # Annotate with seasonality / holiday flag
    from seasonality import is_holiday_period
    if not alerts.empty:
        alerts["holiday_period"] = is_holiday_period(as_of)
    # Annotate with campaign context
    if "campanas" in data and not alerts.empty:
        in_window, name = in_campaign_window(as_of, data["campanas"])
        alerts["campaign_active"] = in_window
        alerts["campaign_name"] = name if in_window else ""

        # Post-campaign grace: suppress silent / churn alerts for clients still
        # in their inventory window from a heavy campaign-window purchase
        grace_keys = post_campaign_grace_keys(v, data["campanas"], as_of)
        if grace_keys:
            silent_or_churn = alerts["tipo_alerta"].isin(["silent", "churn_risk"])
            in_grace = alerts.apply(
                lambda r: (r["id_cliente"], r["familia"]) in grace_keys, axis=1)
            alerts["post_campaign_grace"] = silent_or_churn & in_grace
            alerts = alerts[~alerts["post_campaign_grace"]].drop(columns=["post_campaign_grace"]).reset_index(drop=True)
    return alerts


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2025-12-29"
    alerts = generate_alerts(date)
    print(f"Generated {len(alerts):,} alerts for {date}")
    print(f"Total impact: €{alerts['expected_impact_eur'].sum():,.0f}")
    print(alerts.head(5).to_string())

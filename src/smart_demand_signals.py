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
def _commodity_alert(r):
    seg = r["segment"]
    if seg == "lost":
        rec = r["recency_days"] if pd.notna(r["recency_days"]) else 365
        impact = max(0.0, r["volume_eur_baseline"]) * 0.3   # discounted — recovery is hard
        urg = 0.2  # low urgency
        conv = 0.10  # already lost — recovery is unlikely
        tipo = "lost"
        motivo = f"Cliente perdido (>{int(rec)}d sin compra): campaña de recuperación"
        prio = "Low"
        canal, win = "televenta", 90
    elif seg == "promiscuous":
        impact = max(0.0, (r["potencial_h"] or 0) - r["volume_eur_current"])
        urg, tipo = 0.7, "capture_window"
        # conversion_probability: closer to loyal = higher prob (capped at 1.0)
        share = r["share_of_potential"] or 0
        conv = min(1.0, max(0.10, share / 0.30))
        motivo = (f"Cliente promiscuo: capturado {share:.0%} del potencial; "
                  f"€{impact:,.0f} de demanda desviada a competencia")
        prio = "High" if impact > 1500 else ("Medium" if impact > 500 else "Low")
        canal = "delegado" if prio == "High" else "televenta"
        win = 7 if prio == "High" else (30 if prio == "Medium" else 90)
    elif seg == "churn_risk_silent":
        impact = max(0.0, r["volume_eur_baseline"])
        rec = r["recency_days"] if pd.notna(r["recency_days"]) else 365
        urg = max(0.2, 1.0 - max(0, rec - 180) / 365)
        # conversion decays with recency — recoverable in first 6 months
        conv = max(0.10, 1.0 - max(0, rec - 90) / 365)
        tipo = "silent"
        motivo = f"Cliente leal silencioso: €{impact:,.0f}/año en baseline; sin compra desde {rec:.0f}d"
        prio = "High" if (impact > 1000 and rec < 365) else "Medium"
        canal = "delegado" if prio == "High" else "televenta"
        win = 7 if prio == "High" else 30
    else:  # churn_risk_dropping
        impact = max(0.0, r["volume_eur_baseline"] - r["volume_eur_current"])
        urg, tipo = 0.9, "churn_risk"
        # still buying, just less — high conversion if caught early
        conv = 0.65
        motivo = f"Caída sostenida: €{r['volume_eur_baseline']:,.0f}→€{r['volume_eur_current']:,.0f}"
        prio = "High" if impact > 1500 else "Medium"
        canal = "delegado" if prio == "High" else "televenta"
        win = 7 if prio == "High" else 30
    return tipo, motivo, prio, impact, urg, canal, win, conv


def _technical_alert(r):
    pat = r["pattern"]
    if pat == "systematic_deterioration":
        impact = max(0.0, r["expected_vol_recent"] - r["volume_recent"]) * 4
        urg, tipo = 0.95, "churn_risk"
        conv = 0.55  # active and slipping — moderate recovery odds
        motivo = (f"Cliente sistemático deteriorándose: €{r['volume_recent']:,.0f} vs "
                  f"esperado €{r['expected_vol_recent']:,.0f}")
        prio = "High" if impact > 2000 else "Medium"
        canal, win = "delegado", 7
    elif pat == "systematic_silent":
        ls = r["lifespan_days"] if pd.notna(r["lifespan_days"]) and r["lifespan_days"] > 0 else 365
        annual = (r["lifetime_volume"] / ls) * 365
        impact = max(0.0, annual)
        rec = r["recency_days"]
        urg = max(0.2, 1.0 - max(0, rec - 180) / 365)
        conv = max(0.10, 1.0 - max(0, rec - 90) / 365)
        tipo = "silent"
        motivo = f"Cliente sistemático silencioso: ~€{annual:,.0f}/año en histórico, sin compra {rec:.0f}d"
        prio = "High" if (impact > 5000 and rec < 365) else "Medium"
        canal, win = "delegado", (7 if prio == "High" else 30)
    elif pat == "occasional_silent":
        impact = max(0.0, r["volume_baseline"])
        urg, tipo = 0.5, "silent"
        conv = 0.30  # occasional buyers reactivate less reliably
        motivo = f"Cliente ocasional sin compra reciente: €{impact:,.0f} en período baseline"
        prio = "Medium" if impact > 500 else "Low"
        canal, win = "televenta", (30 if prio == "Medium" else 90)
    else:  # spike
        impact = max(0.0, r["volume_recent"] - r["expected_vol_recent"])
        urg, tipo = 0.4, "opportunity_spike"
        conv = 0.50  # half are real, half are noise
        motivo = (f"Pico anómalo: €{r['volume_recent']:,.0f} vs esperado €{r['expected_vol_recent']:,.0f} "
                  f"— investigar oportunidad")
        prio = "Medium" if impact > 1000 else "Low"
        canal = "delegado" if prio == "Medium" else "televenta"
        win = 30
    return tipo, motivo, prio, impact, urg, canal, win, conv


def build_alerts(comm_seg: pd.DataFrame, tech_pat: pd.DataFrame,
                 clientes: pd.DataFrame, mapping: pd.DataFrame,
                 as_of: pd.Timestamp) -> pd.DataFrame:
    fam_map = dict(zip(mapping["categoria_h"], mapping["familia_comercial"]))
    rows = []

    for _, r in comm_seg[comm_seg["segment"].isin(
            ["promiscuous", "churn_risk_silent", "churn_risk_dropping", "lost"])].iterrows():
        tipo, motivo, prio, impact, urg, canal, win, conv = _commodity_alert(r)
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
            "systematic_spike", "occasional_spike"])].iterrows():
        tipo, motivo, prio, impact, urg, canal, win, conv = _technical_alert(r)
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

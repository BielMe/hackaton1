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
    }


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
        s = r["share_of_potential"]
        if base > 0 and curr <= 0: return "churn_risk_silent"
        if base > 0 and curr < 0.5 * base: return "churn_risk_dropping"
        if pot is None or pd.isna(pot) or pot == 0: return "unknown_potential"
        if s >= 0.30: return "loyal"
        if s < 0.05: return "marginal"
        return "promiscuous"

    agg["segment"] = agg.apply(label, axis=1)
    return agg


def technical_patterns(v: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Per (cliente × familia_h) for technical products. Individual-baseline rule."""
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
    df = (lt.merge(wr, on=["id_cliente", "familia_h"], how="left")
            .merge(wb, on=["id_cliente", "familia_h"], how="left")
            .fillna({"frequency_recent": 0, "volume_recent": 0,
                     "frequency_baseline": 0, "volume_baseline": 0}))

    df["expected_freq_recent"] = df["frequency_baseline"] * (90 / 275)
    df["expected_vol_recent"] = df["volume_baseline"] * (90 / 275)
    df["freq_drop_ratio"] = df.apply(
        lambda r: r["frequency_recent"] / r["expected_freq_recent"]
        if r["expected_freq_recent"] > 0 else None, axis=1)
    df["vol_drop_ratio"] = df.apply(
        lambda r: r["volume_recent"] / r["expected_vol_recent"]
        if r["expected_vol_recent"] > 0 else None, axis=1)

    df["signal_absent"] = df["frequency_recent"] == 0
    df["signal_drop_freq"] = df["expected_freq_recent"].gt(0) & (df["freq_drop_ratio"].fillna(1) < 0.5)
    df["signal_drop_volume"] = df["expected_vol_recent"].gt(0) & (df["vol_drop_ratio"].fillna(1) < 0.5)
    df["signal_anomaly_high"] = df["expected_vol_recent"].gt(0) & (df["vol_drop_ratio"].fillna(0) > 2.0)

    def pattern(r):
        if r["purchase_days_total"] < 3: return "insufficient_history"
        sys = pd.notna(r["mean_interpurchase_days"]) and r["mean_interpurchase_days"] <= 90
        if sys:
            if r["signal_absent"]: return "systematic_silent"
            if r["signal_drop_freq"] or r["signal_drop_volume"]: return "systematic_deterioration"
            if r["signal_anomaly_high"]: return "systematic_spike"
            return "systematic_active"
        if r["signal_absent"] and r["frequency_baseline"] > 0: return "occasional_silent"
        if r["signal_absent"]: return "occasional_dormant"
        if r["signal_anomaly_high"]: return "occasional_spike"
        return "occasional_active"

    df["pattern"] = df.apply(pattern, axis=1)
    return df


# -------------------- ACTIVATION LAYER --------------------
def _commodity_alert(r):
    seg = r["segment"]
    if seg == "promiscuous":
        impact = max(0.0, (r["potencial_h"] or 0) - r["volume_eur_current"])
        urg, tipo = 0.7, "capture_window"
        motivo = (f"Cliente promiscuo: capturado {r['share_of_potential']:.0%} del potencial; "
                  f"€{impact:,.0f} de demanda desviada a competencia")
        prio = "High" if impact > 1500 else ("Medium" if impact > 500 else "Low")
        canal = "delegado" if prio == "High" else "televenta"
        win = 7 if prio == "High" else (30 if prio == "Medium" else 90)
    elif seg == "churn_risk_silent":
        impact = max(0.0, r["volume_eur_baseline"])
        rec = r["recency_days"] if pd.notna(r["recency_days"]) else 365
        urg = max(0.2, 1.0 - max(0, rec - 180) / 365)
        tipo = "silent"
        motivo = f"Cliente leal silencioso: €{impact:,.0f}/año en baseline; sin compra desde {rec:.0f}d"
        prio = "High" if (impact > 1000 and rec < 365) else "Medium"
        canal = "delegado" if prio == "High" else "televenta"
        win = 7 if prio == "High" else 30
    else:  # churn_risk_dropping
        impact = max(0.0, r["volume_eur_baseline"] - r["volume_eur_current"])
        urg, tipo = 0.9, "churn_risk"
        motivo = f"Caída sostenida: €{r['volume_eur_baseline']:,.0f}→€{r['volume_eur_current']:,.0f}"
        prio = "High" if impact > 1500 else "Medium"
        canal = "delegado" if prio == "High" else "televenta"
        win = 7 if prio == "High" else 30
    return tipo, motivo, prio, impact, urg, canal, win


def _technical_alert(r):
    pat = r["pattern"]
    if pat == "systematic_deterioration":
        impact = max(0.0, r["expected_vol_recent"] - r["volume_recent"]) * 4
        urg, tipo = 0.95, "churn_risk"
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
        tipo = "silent"
        motivo = f"Cliente sistemático silencioso: ~€{annual:,.0f}/año en histórico, sin compra {rec:.0f}d"
        prio = "High" if (impact > 5000 and rec < 365) else "Medium"
        canal, win = "delegado", (7 if prio == "High" else 30)
    elif pat == "occasional_silent":
        impact = max(0.0, r["volume_baseline"])
        urg, tipo = 0.5, "silent"
        motivo = f"Cliente ocasional sin compra reciente: €{impact:,.0f} en período baseline"
        prio = "Medium" if impact > 500 else "Low"
        canal, win = "televenta", (30 if prio == "Medium" else 90)
    else:  # spike
        impact = max(0.0, r["volume_recent"] - r["expected_vol_recent"])
        urg, tipo = 0.4, "opportunity_spike"
        motivo = (f"Pico anómalo: €{r['volume_recent']:,.0f} vs esperado €{r['expected_vol_recent']:,.0f} "
                  f"— investigar oportunidad")
        prio = "Medium" if impact > 1000 else "Low"
        canal = "delegado" if prio == "Medium" else "televenta"
        win = 30
    return tipo, motivo, prio, impact, urg, canal, win


def build_alerts(comm_seg: pd.DataFrame, tech_pat: pd.DataFrame,
                 clientes: pd.DataFrame, mapping: pd.DataFrame,
                 as_of: pd.Timestamp) -> pd.DataFrame:
    fam_map = dict(zip(mapping["categoria_h"], mapping["familia_comercial"]))
    rows = []

    for _, r in comm_seg[comm_seg["segment"].isin(
            ["promiscuous", "churn_risk_silent", "churn_risk_dropping"])].iterrows():
        tipo, motivo, prio, impact, urg, canal, win = _commodity_alert(r)
        rows.append({
            "id_cliente": r["id_cliente"],
            "bloque_analitico": "Commodities",
            "categoria_h": r["categoria_h"],
            "familia": r["categoria_h"],
            "familia_comercial": fam_map.get(r["categoria_h"]),
            "segment_or_pattern": r["segment"],
            "tipo_alerta": tipo, "motivo": motivo, "prioridad": prio,
            "expected_impact_eur": impact, "urgency_factor": urg,
            "canal_recomendado": canal, "contact_window_days": win,
            "trace_features": json.dumps({
                "segment": r["segment"],
                "share_of_potential": float(r["share_of_potential"]) if pd.notna(r["share_of_potential"]) else None,
                "potencial_h": float(r["potencial_h"]),
                "volume_eur_current": float(r["volume_eur_current"]),
                "volume_eur_baseline": float(r["volume_eur_baseline"]),
                "recency_days": float(r["recency_days"]) if pd.notna(r["recency_days"]) else None,
            }),
        })

    for _, r in tech_pat[tech_pat["pattern"].isin([
            "systematic_deterioration", "systematic_silent", "occasional_silent",
            "systematic_spike", "occasional_spike"])].iterrows():
        tipo, motivo, prio, impact, urg, canal, win = _technical_alert(r)
        rows.append({
            "id_cliente": r["id_cliente"],
            "bloque_analitico": "Productos Técnicos",
            "categoria_h": "Categoria T1",
            "familia": r["familia_h"],
            "familia_comercial": "Biomateriales (técnicos)",
            "segment_or_pattern": r["pattern"],
            "tipo_alerta": tipo, "motivo": motivo, "prioridad": prio,
            "expected_impact_eur": impact, "urgency_factor": urg,
            "canal_recomendado": canal, "contact_window_days": win,
            "trace_features": json.dumps({
                "pattern": r["pattern"],
                "recency_days": float(r["recency_days"]) if pd.notna(r["recency_days"]) else None,
                "frequency_recent": int(r["frequency_recent"]),
                "frequency_baseline": int(r["frequency_baseline"]),
                "volume_recent": float(r["volume_recent"]),
                "expected_vol_recent": float(r["expected_vol_recent"]),
                "mean_interpurchase_days": float(r["mean_interpurchase_days"]) if pd.notna(r["mean_interpurchase_days"]) else None,
                "lifetime_volume": float(r["lifetime_volume"]),
            }),
        })

    a = pd.DataFrame(rows)
    if a.empty:
        return a
    a["score"] = a["expected_impact_eur"] * a["urgency_factor"]
    a["fecha_alerta"] = as_of.date()
    a = a.merge(clientes[["id_cliente", "provincia"]], on="id_cliente", how="left")
    a = a.sort_values("score", ascending=False).reset_index(drop=True)
    a["alert_id"] = [f"ALT-{as_of.strftime('%Y%m%d')}-{i+1:06d}" for i in range(len(a))]
    return a[[
        "alert_id", "fecha_alerta", "id_cliente", "provincia",
        "bloque_analitico", "categoria_h", "familia", "familia_comercial",
        "tipo_alerta", "motivo", "segment_or_pattern",
        "prioridad", "score", "expected_impact_eur", "urgency_factor",
        "canal_recomendado", "contact_window_days", "trace_features",
    ]]


# -------------------- ENTRY POINT --------------------
def generate_alerts(as_of_date, data: dict | None = None) -> pd.DataFrame:
    """
    Generate the daily alert table for a given as-of date.

    Parameters
    ----------
    as_of_date : str | pd.Timestamp
        Reference date. Only data on/before this date is used.
    data : dict, optional
        Pre-loaded dict from `load_data()`. If None, will load fresh.

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
    return build_alerts(cs, tp, data["clientes"], data["mapping"], as_of)


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2025-12-29"
    alerts = generate_alerts(date)
    print(f"Generated {len(alerts):,} alerts for {date}")
    print(f"Total impact: €{alerts['expected_impact_eur'].sum():,.0f}")
    print(alerts.head(5).to_string())

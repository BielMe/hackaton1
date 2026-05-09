"""
Smart Demand Signals — interactive demo dashboard.

Run with:
    streamlit run src/dashboard.py
"""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
import sys; sys.path.insert(0, str(ROOT / "src"))
from smart_demand_signals import generate_alerts, load_data
from learning_loop import compute_metrics, recommend_threshold_adjustments
from crm_export import export_alerts

st.set_page_config(page_title="Smart Demand Signals", layout="wide", page_icon="📊")

# ----- Data loading (cached) -----
@st.cache_data(show_spinner="Loading data...")
def _load():
    return load_data()

@st.cache_data(show_spinner="Generating alerts...")
def _alerts(date_str: str):
    return generate_alerts(date_str, data=_load())

# ----- Sidebar controls -----
st.sidebar.title("⚙️ Controls")
data = _load()
min_date = data["ventas"]["fecha"].min().date()
max_date = data["ventas"]["fecha"].max().date()

ref = st.sidebar.date_input("Reference date (as-of)",
                            value=max_date, min_value=min_date, max_value=max_date)
alerts = _alerts(ref.isoformat())

st.sidebar.markdown("---")
st.sidebar.markdown("### Filters (Alerts tab)")
prio_filter = st.sidebar.multiselect("Prioridad",
                                     options=sorted(alerts["prioridad"].unique()),
                                     default=["High", "Medium"])
tipo_filter = st.sidebar.multiselect("Tipo de alerta",
                                     options=sorted(alerts["tipo_alerta"].unique()),
                                     default=sorted(alerts["tipo_alerta"].unique()))
canal_filter = st.sidebar.multiselect("Canal",
                                      options=sorted(alerts["canal_recomendado"].unique()),
                                      default=sorted(alerts["canal_recomendado"].unique()))
bloque_filter = st.sidebar.multiselect("Bloque analítico",
                                       options=sorted(alerts["bloque_analitico"].unique()),
                                       default=sorted(alerts["bloque_analitico"].unique()))
client_search = st.sidebar.text_input("🔍 Cliente search (id_cliente)", value="")

f = alerts[
    alerts["prioridad"].isin(prio_filter)
    & alerts["tipo_alerta"].isin(tipo_filter)
    & alerts["canal_recomendado"].isin(canal_filter)
    & alerts["bloque_analitico"].isin(bloque_filter)
]
if client_search.strip():
    f = f[f["id_cliente"].str.contains(client_search.strip(), case=False, na=False)]

# ----- Header -----
st.title("📊 Smart Demand Signals")
st.markdown(f"**Inibsa · Interhack BCN 2026** — Daily alert generator for {ref}")

tab_alerts, tab_learning, tab_profile = st.tabs(["📋 Alerts", "📈 Learning loop", "🔍 Client profile"])

# ====================================================================
# TAB 1 — Alerts
# ====================================================================
with tab_alerts:
    # Campaign banner if as-of date falls in a campaign window
    if not alerts.empty and bool(alerts["campaign_active"].iloc[0]):
        cname = alerts["campaign_name"].iloc[0]
        st.info(f"🎯 **Campaign window active: `{cname}`** — alerts firing during a campaign "
                f"may include campaign-driven volume noise. Treat anomaly_high signals "
                f"with extra scrutiny.", icon="🎯")

    # Holiday banner — explains why some drop signals were suppressed
    if not alerts.empty and bool(alerts["holiday_period"].iloc[0]):
        st.info(f"🏖️ **Holiday period active** (August / Christmas week / Reyes) — "
                f"technical-product drops are suppressed unless YoY comparison also "
                f"shows a >50% decline. Avoids treating seasonal pauses as churn.",
                icon="🏖️")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total alerts", f"{len(f):,}", delta=f"of {len(alerts):,} unfiltered")
    c2.metric("High priority", f"{(f['prioridad']=='High').sum():,}")
    c3.metric("Expected impact", f"€{f['expected_impact_eur'].sum():,.0f}")
    c4.metric("Top alert score", f"{f['score'].max():,.0f}" if len(f) else "—")

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("##### By tipo de alerta")
        chart_data = f["tipo_alerta"].value_counts().reset_index()
        chart_data.columns = ["tipo_alerta", "count"]
        st.bar_chart(chart_data, x="tipo_alerta", y="count")
    with col_b:
        st.markdown("##### By canal × prioridad")
        cross = pd.crosstab(f["canal_recomendado"], f["prioridad"])
        st.bar_chart(cross)

    # Province distribution
    if len(f):
        st.markdown("##### Alerts by provincia (top 15)")
        prov_counts = f["provincia"].value_counts().head(15).reset_index()
        prov_counts.columns = ["provincia", "n_alerts"]
        st.bar_chart(prov_counts, x="provincia", y="n_alerts")

    st.markdown("### Top alerts (sorted by score)")
    top_n = st.slider("How many to show", min_value=10, max_value=200, value=25, step=5)

    table_cols = ["alert_id", "id_cliente", "provincia", "familia", "tipo_alerta",
                  "loyalty_tier", "trend", "prioridad", "score",
                  "expected_impact_eur", "urgency_factor", "conversion_probability",
                  "canal_recomendado", "contact_window_days", "motivo"]
    display = f.head(top_n)[table_cols].copy()
    display["score"] = display["score"].map(lambda x: f"{x:,.0f}")
    display["expected_impact_eur"] = display["expected_impact_eur"].map(lambda x: f"€{x:,.0f}")
    display["urgency_factor"] = display["urgency_factor"].map(lambda x: f"{x:.2f}")
    display["conversion_probability"] = display["conversion_probability"].map(lambda x: f"{x:.2f}")
    st.dataframe(display, use_container_width=True, hide_index=True)

    # Export buttons
    if len(f):
        ex_col1, ex_col2 = st.columns(2)
        with ex_col1:
            st.download_button(
                "⬇️ Download filtered alerts (CSV)",
                data=f.to_csv(index=False).encode("utf-8"),
                file_name=f"alerts_{ref}.csv",
                mime="text/csv",
            )
        with ex_col2:
            payloads = export_alerts(f.head(top_n), target="hubspot")
            st.download_button(
                "⬇️ Export top-N as HubSpot Tasks (JSON)",
                data=json.dumps(payloads, indent=2, ensure_ascii=False).encode("utf-8"),
                file_name=f"alerts_hubspot_{ref}.json",
                mime="application/json",
            )

    st.markdown("### 🔍 Drill into a single alert")
    selected_id = st.selectbox("Pick an alert_id", options=f["alert_id"].head(top_n).tolist())
    if selected_id:
        row = f[f["alert_id"] == selected_id].iloc[0]
        cc1, cc2 = st.columns([2, 1])
        with cc1:
            st.markdown(f"**Cliente:** `{row['id_cliente']}`  ·  **Provincia:** {row['provincia']}")
            st.markdown(f"**Familia:** {row['familia']} ({row['familia_comercial']}) · "
                        f"**Bloque:** {row['bloque_analitico']}")
            st.markdown(f"**Tipo:** `{row['tipo_alerta']}` · **Prioridad:** `{row['prioridad']}` · "
                        f"**Canal:** `{row['canal_recomendado']}`")
            st.markdown(f"**Motivo:** {row['motivo']}")
            st.markdown(f"**Ventana de contacto:** {row['contact_window_days']} días")
        with cc2:
            st.metric("Score", f"{row['score']:,.0f}")
            st.metric("Impact (€)", f"€{row['expected_impact_eur']:,.0f}")
            st.metric("Urgency × Conv prob", f"{row['urgency_factor']:.2f} × {row['conversion_probability']:.2f}")
        st.markdown("**🧩 Trace features (why this alert fired):**")
        trace = json.loads(row["trace_features"])
        st.json(trace)

# ====================================================================
# TAB 2 — Learning loop
# ====================================================================
with tab_learning:
    st.markdown("### Outcome-driven feedback loop")

    st.warning(
        "⚠️ **Demo data — not real outcomes.** The 120 rows in "
        "`analysis/alert_outcomes.csv` are a calibrated simulation built to "
        "demonstrate the feedback loop. In production, outcomes would be fed "
        "by CRM webhooks (HubSpot / Salesforce), sales-team workflow tools, or "
        "a manual logging form. The schema, module, and dashboard are real; "
        "only the rows are illustrative.",
        icon="⚠️",
    )

    metrics = compute_metrics()

    if metrics.get("empty"):
        st.info("No outcomes recorded yet — collect feedback to enable this view.")
    else:
        h = metrics["headline"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Outcomes recorded", f"{h['n_outcomes_total']:,}",
                  delta=f"of {h['n_alerts_total']:,} alerts")
        m2.metric("Conversion rate", f"{h['overall_conversion']:.1%}")
        m3.metric("False-positive rate", f"{h['false_positive_rate']:.1%}")
        m4.metric("Revenue captured", f"€{h['revenue_captured_eur']:,.0f}")

        st.markdown("---")
        st.markdown("##### Conversion by alert type")
        bt = metrics["by_tipo"][[
            "tipo_alerta", "n_outcomes", "n_won",
            "conversion_rate", "false_positive_rate",
            "revenue_captured_eur", "avg_revenue_per_won"
        ]].copy()
        bt["conversion_rate"]      = bt["conversion_rate"].map(lambda x: f"{x:.1%}")
        bt["false_positive_rate"]  = bt["false_positive_rate"].map(lambda x: f"{x:.1%}")
        bt["revenue_captured_eur"] = bt["revenue_captured_eur"].map(lambda x: f"€{x:,.0f}")
        bt["avg_revenue_per_won"]  = bt["avg_revenue_per_won"].map(
            lambda x: f"€{x:,.0f}" if pd.notna(x) else "—")
        st.dataframe(bt, use_container_width=True, hide_index=True)

        st.markdown("---")
        ll, rr = st.columns(2)
        with ll:
            st.markdown("##### Effectiveness by canal")
            bc = metrics["by_canal"].copy()
            bc["conversion_rate"]      = bc["conversion_rate"].map(lambda x: f"{x:.1%}")
            bc["revenue_captured_eur"] = bc["revenue_captured_eur"].map(lambda x: f"€{x:,.0f}")
            st.dataframe(bc, use_container_width=True, hide_index=True)
        with rr:
            st.markdown("##### False-positive reasons (top)")
            fp = metrics["false_positive_reasons"]
            if len(fp):
                st.dataframe(fp, use_container_width=True, hide_index=True)
            else:
                st.write("No false positives recorded.")

        st.markdown("---")
        st.markdown("##### 🎯 Recommended threshold adjustments")
        for r in recommend_threshold_adjustments():
            st.markdown(f"- {r}")

        st.markdown("---")
        st.markdown("##### How the loop closes")
        st.code(
"""Alert fires  →  Sales action  →  Outcome recorded
                       ↓
               Metrics aggregated
                       ↓
Threshold recommendations  →  Rule update  →  Better alerts""",
            language="text",
        )
        st.caption("Each outcome adds one row to `analysis/alert_outcomes.csv`. "
                   "The system never silently drops feedback — every recorded outcome "
                   "appears here on next refresh.")

# ====================================================================
# TAB 3 — Client profile (drill into one clinic's full story)
# ====================================================================
with tab_profile:
    st.markdown("### Single-client deep dive")
    st.caption("Pick a clinic. See everything the system knows about them: alerts "
               "across product families, segmentation, purchase history.")

    suggested = (alerts.groupby("id_cliente")["score"].sum()
                 .sort_values(ascending=False).head(20).index.tolist())
    pick = st.selectbox("Pick a client (top 20 by aggregate score)", options=suggested)
    typed = st.text_input("...or type any id_cliente", value="")
    target = (typed.strip() or pick) if (typed.strip() or pick) else None

    if target:
        # Header info from Clientes
        cli = data["clientes"]
        cli_row = cli[cli["id_cliente"].astype(str) == str(target)]
        if cli_row.empty:
            st.warning(f"Client `{target}` not in registered Clientes table — "
                       f"could be `cliente_no_registrado=True` (delegated client).")
        else:
            cli_row = cli_row.iloc[0]
            h1, h2, h3 = st.columns(3)
            h1.metric("Cliente", str(target))
            h2.metric("Provincia", cli_row["provincia"])
            h3.metric("Código postal", cli_row["codigo_postal"])

        # All alerts for this client right now
        st.markdown("---")
        st.markdown("##### Active alerts (today)")
        cli_alerts = alerts[alerts["id_cliente"].astype(str) == str(target)]
        if cli_alerts.empty:
            st.success("No active alerts — this client is healthy across all product families.")
        else:
            view = cli_alerts[["familia", "tipo_alerta", "loyalty_tier", "trend",
                               "prioridad", "score", "expected_impact_eur",
                               "conversion_probability", "motivo"]].copy()
            view["score"] = view["score"].map(lambda x: f"{x:,.0f}")
            view["expected_impact_eur"] = view["expected_impact_eur"].map(lambda x: f"€{x:,.0f}")
            view["conversion_probability"] = view["conversion_probability"].map(lambda x: f"{x:.2f}")
            st.dataframe(view, use_container_width=True, hide_index=True)

        # Purchase history chart
        st.markdown("---")
        st.markdown("##### Purchase history")
        v = data["ventas"]
        cli_ventas = v[(v["id_cliente"].astype(str) == str(target))
                       & (v["tipo_transaccion"] == "venta")].copy()
        if cli_ventas.empty:
            st.info("No purchase history found.")
        else:
            cli_ventas["fecha"] = pd.to_datetime(cli_ventas["fecha"])
            cli_ventas["mes"] = cli_ventas["fecha"].dt.to_period("M").astype(str)
            monthly = (cli_ventas.groupby(["mes", "bloque_analitico"])["valores_h"]
                       .sum().reset_index())
            pivot = monthly.pivot(index="mes", columns="bloque_analitico",
                                  values="valores_h").fillna(0)
            st.bar_chart(pivot, height=300)
            ph1, ph2, ph3 = st.columns(3)
            ph1.metric("Lifetime €", f"€{cli_ventas['valores_h'].sum():,.0f}")
            ph2.metric("Total purchases", f"{len(cli_ventas):,}")
            ph3.metric("Last purchase", cli_ventas["fecha"].max().date().isoformat())

        # Segmentation snapshot
        st.markdown("---")
        st.markdown("##### Segmentation across product families")
        v_filtered = data["ventas"][
            (~data["ventas"]["cliente_no_registrado"])
            & (data["ventas"]["tipo_transaccion"].isin(["venta", "devolucion"]))
            & (data["ventas"]["fecha"] <= pd.Timestamp(ref))
        ]
        from smart_demand_signals import commodity_segments, technical_patterns
        cs = commodity_segments(v_filtered, data["potencial"], pd.Timestamp(ref))
        tp = technical_patterns(v_filtered, pd.Timestamp(ref))
        cs_cli = cs[cs["id_cliente"].astype(str) == str(target)]
        tp_cli = tp[tp["id_cliente"].astype(str) == str(target)]
        cs_view = cs_cli[["categoria_h", "segment", "loyalty_tier", "trend",
                          "share_of_potential", "volume_eur_current",
                          "volume_eur_baseline", "potencial_h", "recency_days"]]
        tp_view = tp_cli[["familia_h", "pattern", "trend", "recency_days",
                          "frequency_recent", "volume_recent",
                          "expected_vol_recent", "lifetime_volume"]]
        st.markdown("**Commodities**")
        st.dataframe(cs_view if len(cs_view) else pd.DataFrame({"info": ["no commodity activity"]}),
                     use_container_width=True, hide_index=True)
        st.markdown("**Productos Técnicos**")
        st.dataframe(tp_view if len(tp_view) else pd.DataFrame({"info": ["no technical activity"]}),
                     use_container_width=True, hide_index=True)

# ----- Footer -----
st.markdown("---")
with st.expander("ℹ️ Architecture (data → analytical → activation → feedback layers)"):
    st.markdown("""
    **Data layer** — cleaned CSVs in `std_data/csv/` (5 sheets: Ventas, Clientes, Productos, Potencial, Campañas)

    **Analytical layer** — two segmentation modules:
    - *Commodities*: share-of-potential rule → loyal / promiscuous / marginal / churn_risk
    - *Technical*: individual-baseline rule (90d vs 91-365d) → systematic_active / silent / deterioration / occasional_*

    **Activation layer** — alert generator emitting:
    - `id_cliente × familia × tipo_alerta × motivo × prioridad × score × canal × ventana × trace_features`
    - Sorted by `score = expected_impact_eur × urgency_factor`
    - Routed to `delegado` / `televenta` based on priority

    **Feedback layer** — `alert_outcomes.csv` records action + result per alert, fed back into:
    - Conversion rate per `tipo_alerta` (precision)
    - False-positive flagging
    - Threshold-tuning recommendations

    **Daily cadence** — `generate_alerts(as_of_date)` recomputes alerts for any date.
    """)

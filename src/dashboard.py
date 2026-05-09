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

st.set_page_config(page_title="Smart Demand Signals", layout="wide", page_icon="📊")

# ----- Data loading (cached) -----
@st.cache_data(show_spinner="Loading data...")
def _load():
    return load_data()

@st.cache_data(show_spinner="Generating alerts...")
def _alerts(date_str: str):
    return generate_alerts(date_str, data=_load())

# ----- Sidebar controls -----
# ----- Sidebar controls & RLS (Row-Level Security) -----
st.sidebar.title("⚙️ Controls")

# MOCK DE SEGURETAT PER ROLS
st.sidebar.markdown("### 👤 Sessió d'Usuari")
rol_usuari = st.sidebar.selectbox(
    "Selecciona la teva zona (Rol):", 
    ["Direcció (Totes les zones)", "Delegació Catalunya", "Delegació Centre", "Delegació Sud"]
)

data = _load()
min_date = data["ventas"]["fecha"].min().date()
max_date = data["ventas"]["fecha"].max().date()

ref = st.sidebar.date_input("Reference date (as-of)",
                            value=max_date, min_value=min_date, max_value=max_date)
alerts = _alerts(ref.isoformat())

# APLICAR FILTRE DE ROL A LES ALERTES
if rol_usuari == "Delegació Catalunya":
    alerts = alerts[alerts['provincia'].isin(["Barcelona", "Tarragona", "Lleida", "Girona"])]
elif rol_usuari == "Delegació Centre":
    alerts = alerts[alerts['provincia'].isin(["Madrid", "Toledo", "Segovia", "Guadalajara"])]
elif rol_usuari == "Delegació Sud":
    alerts = alerts[alerts['provincia'].isin(["Sevilla", "Málaga", "Cádiz", "Córdoba", "Huelva", "Jaén", "Almería", "Granada"])]

st.sidebar.markdown("---")
st.sidebar.markdown("### Filters")
prio_filter = st.sidebar.multiselect("Prioridad",
                                     options=sorted(alerts["prioridad"].unique()),
                                     default=["High", "Medium"])
tipo_filter = st.sidebar.multiselect("Tipo de alerta",
                                     options=sorted(alerts["tipo_alerta"].unique()),
                                     default=sorted(alerts["tipo_alerta"].unique()))

alerts = alerts[alerts["prioridad"].isin(prio_filter) & alerts["tipo_alerta"].isin(tipo_filter)]

# EXPORTACIÓ ACCIONABLE (CSV Download)
st.sidebar.markdown("---")
st.sidebar.markdown("### 📥 Exportar Dades")
csv_data = alerts.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="Descarregar Llistat (CSV)",
    data=csv_data,
    file_name=f"smart_signals_{ref}_{rol_usuari.replace(' ', '_')}.csv",
    mime='text/csv',
    help="Descarrega les alertes filtrades per importar-les al CRM o Excel."
)

# ----- Header -----
st.title("📊 Smart Demand Signals")
st.markdown(f"**Inibsa · Interhack BCN 2026** — Daily alert generator for {ref}")

# ----- Metric cards -----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total alerts", f"{len(f):,}", delta=f"of {len(alerts):,} unfiltered")
c2.metric("High priority", f"{(f['prioridad']=='High').sum():,}")
c3.metric("Expected impact", f"€{f['expected_impact_eur'].sum():,.0f}")
c4.metric("Top alert score", f"{f['score'].max():,.0f}" if len(f) else "—")

st.markdown("---")

# ----- Distribution charts -----
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

# ----- Top alerts table -----
st.markdown("### Top alerts (sorted by score)")
top_n = st.slider("How many to show", min_value=10, max_value=200, value=25, step=5)

table_cols = ["alert_id", "id_cliente", "provincia", "familia", "tipo_alerta",
              "prioridad", "score", "expected_impact_eur", "urgency_factor",
              "canal_recomendado", "contact_window_days", "motivo"]
display = f.head(top_n)[table_cols].copy()
display["score"] = display["score"].map(lambda x: f"{x:,.0f}")
display["expected_impact_eur"] = display["expected_impact_eur"].map(lambda x: f"€{x:,.0f}")
display["urgency_factor"] = display["urgency_factor"].map(lambda x: f"{x:.2f}")
st.dataframe(display, use_container_width=True, hide_index=True)

# ----- Drill-in -----
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
        st.metric("Urgency", f"{row['urgency_factor']:.2f}")
    st.markdown("**🧩 Trace features (why this alert fired):**")
    trace = json.loads(row["trace_features"])
    st.json(trace)

# ----- Footer -----
st.markdown("---")
with st.expander("ℹ️ Architecture (data → analytical → activation layers)"):
    st.markdown("""
    **Data layer** — cleaned CSVs in `std_data/csv/` (5 sheets: Ventas, Clientes, Productos, Potencial, Campañas)

    **Analytical layer** — two segmentation modules:
    - *Commodities*: share-of-potential rule → loyal / promiscuous / marginal / churn_risk
    - *Technical*: individual-baseline rule (90d vs 91-365d) → systematic_active / silent / deterioration / occasional_*

    **Activation layer** — alert generator emitting:
    - `id_cliente × familia × tipo_alerta × motivo × prioridad × score × canal × ventana × trace_features`
    - Sorted by `score = expected_impact_eur × urgency_factor`
    - Routed to `delegado` / `televenta` based on priority

    **Daily cadence** — `generate_alerts(as_of_date)` recomputes for any date.
    """)

"""
Smart Demand Signals — minimalist dashboard.

Two main views:
  1. Client view  — single-client deep dive with the right action call-out
  2. Monitoring   — KPIs, trends, priority list

Plus:
  3. Learning loop — feedback metrics + threshold suggestions

Run:  streamlit run src/dashboard.py
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from smart_demand_signals import (
    generate_alerts, load_data, build_client_profiles,
    filter_commercial_activity,
)
from learning_loop import compute_metrics, recommend_threshold_adjustments
from crm_export import export_alerts


st.set_page_config(page_title="Smart Demand Signals", layout="wide", page_icon="📊")


# ====================================================================
# 4-CATEGORY MAPPING
# Collapses 5 alert types into 4 sales-team-readable categories.
# ====================================================================
def _map_category(alert_row) -> str:
    tipo = alert_row["tipo_alerta"]
    seg = alert_row.get("segment_or_pattern", "")
    if tipo == "lost":
        return "lost_client"
    if tipo == "churn_risk":
        return "loss_risk"
    if tipo == "silent":
        # occasional_silent → opportunity (not a critical loss)
        # systematic_silent / churn_risk_silent → loss risk
        if seg == "occasional_silent":
            return "sales_opportunity"
        return "loss_risk"
    if tipo in ("capture_window", "opportunity_spike"):
        return "sales_opportunity"
    return "sales_opportunity"


CATEGORY_CONFIG = {
    "lost_client": {
        "label": "LOST CLIENT",
        "color": "red",
        "emoji": "🔴",
        "action": "Periodic reminder — schedule auto-emails every 30 days so the client remembers us",
        "action_short": "Periodic reminder",
    },
    "loss_risk": {
        "label": "LOSS RISK",
        "color": "orange",
        "emoji": "🟠",
        "action": "Urgent visit or call — contact to understand the situation and try to retain the client",
        "action_short": "Urgent visit/call",
    },
    "sales_opportunity": {
        "label": "SALES OPPORTUNITY",
        "color": "orange",
        "emoji": "🟡",
        "action": "Telesales follow-up — contact to offer additional products and explore growth",
        "action_short": "Telesales follow-up",
    },
    "no_risk": {
        "label": "HEALTHY",
        "color": "green",
        "emoji": "🟢",
        "action": "Restock follow-up — schedule a reminder email near the next expected purchase",
        "action_short": "Restock email",
    },
}


# ====================================================================
# CACHED LOADERS
# ====================================================================
@st.cache_data(show_spinner="Loading data...")
def _load():
    return load_data()


@st.cache_data(show_spinner="Generating alerts...")
def _alerts(date_str: str):
    return generate_alerts(date_str, data=_load())


@st.cache_data(show_spinner="Building client profiles...")
def _profiles(date_str: str):
    data = _load()
    v = filter_commercial_activity(data["ventas"], pd.Timestamp(date_str))
    return build_client_profiles(v, data["potencial"], pd.Timestamp(date_str))


# ====================================================================
# HEADER
# ====================================================================
data = _load()
max_date = data["ventas"]["fecha"].max().date()
min_date = data["ventas"]["fecha"].min().date()

top0, top1, top2 = st.columns([0.4, 4, 1])
with top0:
    with st.popover("ℹ️", help="Alert category guide"):
        st.markdown("#### How to read the alerts")
        st.markdown("---")
        st.markdown("##### 🔴 Lost client")
        st.markdown(
            "The client has been **silent for 270+ days** and previously had a regular "
            "purchase pattern. No longer counted as active. "
            "**What to do:** schedule periodic reminders (auto-email every 30 days) to stay top-of-mind.")
        st.markdown("##### 🟠 Loss risk")
        st.markdown(
            "The client **was buying well but has started to slip**: either gone silent (a loyal/"
            "systematic client without recent activity) or volume has dropped >50%. "
            "**What to do:** urgent contact (visit or call) to understand what is happening and retain them.")
        st.markdown("##### 🟡 Sales opportunity")
        st.markdown(
            "There is room to sell more to this client. Could be a **promiscuous client** (buys "
            "from Inibsa and from competitors), an **anomalous activity spike** (bought far more than usual), "
            "or an **occasional client** who has not returned recently. "
            "**What to do:** telesales follow-up to offer products and see if they want to grow with us.")
        st.markdown("##### 🟢 Healthy")
        st.markdown(
            "The client is **buying normally**. No urgent action needed. "
            "**What to do:** schedule a restock email near the next expected purchase to keep the "
            "commercial relationship active.")
        st.markdown("---")
        st.markdown("##### Detail by product family")
        st.markdown(
            "**Commodities** (anaesthesia, needles, disinfection): recurring purchases. We track "
            "the share of potential captured and the trend.\n\n"
            "**Technical products** (biomaterials): more variable purchases. We track whether the pattern "
            "is systematic (≤90d cycle) or occasional, and compare recent activity to a year-ago baseline.")

top1.markdown("## ⚙️ Smart Demand Signals")
ref = top2.date_input("Date", value=max_date, min_value=min_date, max_value=max_date,
                      label_visibility="collapsed")
ref_str = ref.isoformat()

alerts = _alerts(ref_str)
profiles = _profiles(ref_str)

if len(alerts) > 0:
    alerts["category"] = alerts.apply(_map_category, axis=1)


# ====================================================================
# TABS
# ====================================================================
tab_client, tab_monitor, tab_learning = st.tabs([
    "🔍 Client view", "📊 Monitoring", "📈 Learning loop"
])


# ====================================================================
# TAB 1 — CLIENT VIEW
# ====================================================================
with tab_client:
    all_clients = sorted(profiles["id_cliente"].unique()) if len(profiles) > 0 else []
    alerted = set(alerts["id_cliente"].unique()) if len(alerts) > 0 else set()
    ordered = [c for c in all_clients if c in alerted] + [c for c in all_clients if c not in alerted]

    selected = st.selectbox(
        "Client",
        options=ordered,
        format_func=lambda c: f"⚠️ {c}" if c in alerted else c,
        label_visibility="collapsed",
        placeholder="Search a client...",
    )

    if selected:
        cp_row = profiles[profiles["id_cliente"] == selected]
        cl_alerts = alerts[alerts["id_cliente"] == selected] if len(alerts) > 0 else pd.DataFrame()
        cl_info = data["clientes"][data["clientes"]["id_cliente"] == selected]
        prov = cl_info["provincia"].iloc[0] if len(cl_info) > 0 else "—"

        # --- Determine top category ---
        if len(cl_alerts) > 0:
            top_alert = cl_alerts.iloc[0]
            cat = _map_category(top_alert)
        else:
            cat = "no_risk"
        cfg = CATEGORY_CONFIG[cat]

        # --- Banner ---
        st.markdown(f"### {cfg['emoji']} :{cfg['color']}[{cfg['label']}]")
        if len(cl_alerts) > 0:
            st.caption(top_alert["motivo"])
        else:
            st.caption("Active client behaving normally. No alerts on the selected date.")

        # --- Action card ---
        if cat == "no_risk":
            if len(cp_row) > 0:
                cp = cp_row.iloc[0]
                cycle = cp.get("mean_interpurchase_days")
                rec = cp.get("recency_days")
                if pd.notna(cycle) and cycle > 0 and pd.notna(rec):
                    days_left = cycle - rec
                    if days_left > 0:
                        st.success(
                            f"**{cfg['action_short']}** — Estimated restock in **~{days_left:.0f} days**. "
                            f"Schedule a follow-up email for then.")
                    else:
                        st.warning(
                            f"**{cfg['action_short']}** — Client may need restock **now** "
                            f"(avg cycle {cycle:.0f}d, last purchase {rec:.0f}d ago). Send follow-up email.")
                else:
                    st.success(f"**{cfg['action_short']}** — No defined cycle. Send periodic follow-up to maintain the relationship.")
            else:
                st.success(f"**{cfg['action_short']}** — Send periodic follow-up email.")
        elif cat == "lost_client":
            st.error(
                f"**{cfg['action_short']}** — The client has stopped buying. Schedule automatic reminders "
                f"(email every 30 days) so they remember us when they need product again.")
        elif cat == "loss_risk":
            days = top_alert["contact_window_days"] if len(cl_alerts) > 0 else 7
            st.warning(
                f"**{cfg['action_short']}** — Contact within **{days} days**. "
                f"Understand why the client has stopped or reduced and try to retain them.")
        elif cat == "sales_opportunity":
            days = top_alert["contact_window_days"] if len(cl_alerts) > 0 else 30
            st.info(
                f"**{cfg['action_short']}** — Call within **{days} days** to follow up, "
                f"offer additional products and explore whether they want to grow purchases with Inibsa.")

        st.markdown("---")

        # --- Key stats ---
        if len(cp_row) > 0:
            cp = cp_row.iloc[0]

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("📍 Province", prov)
            c2.metric("Last purchase",
                      cp["last_purchase"].strftime("%d/%m/%Y") if pd.notna(cp["last_purchase"]) else "—")

            rec = cp["recency_days"]
            cycle = cp["mean_interpurchase_days"]
            c3.metric("Days since last purchase", f"{rec:.0f}" if pd.notna(rec) else "—")

            if pd.notna(cycle) and cycle > 0:
                c4.metric("Avg cycle", f"{cycle:.0f} days")
                progress = rec / cycle if pd.notna(rec) else 0
                if progress > 1.2:
                    c5.metric("Cycle status", "⚠️ Overdue",
                              delta=f"{(progress - 1) * 100:+.0f}%", delta_color="inverse")
                elif progress > 0.8:
                    c5.metric("Cycle status", "⏳ Due soon",
                              delta=f"{(1 - progress) * cycle:.0f} days left")
                else:
                    c5.metric("Cycle status", "✅ Within window")
            else:
                c4.metric("Avg cycle", "—")
                c5.metric("Cycle status", "—")

            c6, c7, c8 = st.columns(3)
            trend = cp["potential_trend"]
            c6.metric("Trend (6m vs prior)",
                      f"{trend:+.0%}" if pd.notna(trend) else "—",
                      delta=f"{trend:+.0%}" if pd.notna(trend) else None,
                      delta_color="normal" if pd.notna(trend) and trend >= 0 else "inverse")

            sop = cp["share_of_potential"]
            if pd.isna(sop):
                sop_label = "—"
            elif sop > 1:
                sop_label = ">100%"
            else:
                sop_label = f"{sop:.0%}"
            c7.metric("Share of potential (12m)", sop_label,
                      help="Trailing-12-month volume / annual potential. >100% means real sales exceeded the declared estimate.")

            c8.metric("Last 12m volume", f"€{cp['eur_last_12m']:,.0f}")

        st.markdown("---")

        # --- Purchase history chart ---
        v = data["ventas"]
        cl_hist = v[(v["id_cliente"] == selected) & (~v["cliente_no_registrado"])].copy()
        if len(cl_hist) > 0:
            st.markdown("##### Purchase history")
            cl_hist["fecha"] = pd.to_datetime(cl_hist["fecha"])
            cl_hist["month"] = cl_hist["fecha"].dt.to_period("M")
            monthly = cl_hist.groupby("month").agg(total_eur=("valores_h", "sum")).reset_index()
            monthly["month_str"] = monthly["month"].astype(str)
            monthly["3-month avg"] = monthly["total_eur"].rolling(3, min_periods=1).mean()
            chart = monthly.rename(columns={"month_str": "Month", "total_eur": "Sales (€)"})[
                ["Month", "Sales (€)", "3-month avg"]].set_index("Month")
            st.line_chart(chart, height=280)

            with st.expander("By product family"):
                fam = cl_hist.groupby([cl_hist["fecha"].dt.to_period("M"), "familia_h"]).agg(
                    t=("valores_h", "sum")).reset_index()
                fam["m"] = fam["fecha"].astype(str)
                fp = fam.pivot_table(index="m", columns="familia_h", values="t", fill_value=0)
                st.area_chart(fp, height=250)

        # --- Alerts detail ---
        if len(cl_alerts) > 0:
            with st.expander(f"📋 Alert details ({len(cl_alerts)})"):
                for _, a in cl_alerts.iterrows():
                    a_cat = _map_category(a)
                    a_cfg = CATEGORY_CONFIG[a_cat]
                    st.markdown(
                        f"{a_cfg['emoji']} **{a_cfg['label']}** · {a['familia']} · "
                        f"Score {a['score']:,.0f} · {a_cfg['action_short']}"
                    )
                    st.caption(a["motivo"])

        # --- Raw history ---
        with st.expander("📄 Detailed transaction history"):
            if len(cl_hist) > 0:
                show_n = st.slider("Show last N purchases", 10, 100, 20, key="h")
                hd = cl_hist.tail(show_n)[
                    ["fecha", "familia_h", "unidades", "valores_h", "tipo_transaccion"]].copy()
                hd["fecha"] = hd["fecha"].dt.strftime("%d/%m/%Y")
                hd["valores_h"] = hd["valores_h"].map(lambda x: f"€{x:,.2f}")
                hd.columns = ["Date", "Family", "Units", "Amount", "Type"]
                st.dataframe(hd, use_container_width=True, hide_index=True)


# ====================================================================
# TAB 2 — MONITORING
# ====================================================================
with tab_monitor:
    if len(alerts) > 0:
        n_lost = (alerts["category"] == "lost_client").sum()
        n_risk = (alerts["category"] == "loss_risk").sum()
        n_oppt = (alerts["category"] == "sales_opportunity").sum()
    else:
        n_lost = n_risk = n_oppt = 0
    n_healthy = len(profiles) - alerts["id_cliente"].nunique() if len(alerts) > 0 else len(profiles)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🔴 Lost clients", f"{n_lost:,}")
    k2.metric("🟠 Loss risk", f"{n_risk:,}")
    k3.metric("🟡 Opportunities", f"{n_oppt:,}")
    k4.metric("🟢 Healthy", f"{n_healthy:,}", help="Active clients with no active alerts")

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("##### By alert category")
        if len(alerts) > 0:
            cat_c = alerts["category"].value_counts().reset_index()
            cat_c.columns = ["Category", "Count"]
            cat_labels = {
                "lost_client": "🔴 Lost client",
                "loss_risk": "🟠 Loss risk",
                "sales_opportunity": "🟡 Sales opportunity",
            }
            cat_c["Category"] = cat_c["Category"].map(lambda x: cat_labels.get(x, x))
            st.bar_chart(cat_c, x="Category", y="Count", height=280)
    with col_b:
        st.markdown("##### By recommended channel")
        if len(alerts) > 0:
            canal_c = alerts["canal_recomendado"].value_counts().reset_index()
            canal_c.columns = ["Channel", "Alerts"]
            st.bar_chart(canal_c, x="Channel", y="Alerts", height=280)

    st.markdown("---")

    col_p, col_f = st.columns(2)
    with col_p:
        st.markdown("##### By province (top 10)")
        if len(alerts) > 0:
            prov_agg = (alerts.groupby("provincia")
                                .agg(alerts=("alert_id", "count"), impact=("score", "sum"))
                                .reset_index()
                                .sort_values("impact", ascending=False).head(10))
            prov_agg.columns = ["Province", "Alerts", "Impact (€)"]
            prov_agg["Impact (€)"] = prov_agg["Impact (€)"].map(lambda x: f"€{x:,.0f}")
            st.dataframe(prov_agg, use_container_width=True, hide_index=True)
    with col_f:
        st.markdown("##### By product family")
        if len(alerts) > 0:
            fam_agg = (alerts.groupby("familia")
                              .agg(alerts=("alert_id", "count"), impact=("score", "sum"))
                              .reset_index().sort_values("impact", ascending=False))
            fam_agg.columns = ["Family", "Alerts", "Impact (€)"]
            fam_agg["Impact (€)"] = fam_agg["Impact (€)"].map(lambda x: f"€{x:,.0f}")
            st.dataframe(fam_agg, use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Sales evolution ---
    v_filt = filter_commercial_activity(data["ventas"], pd.Timestamp(ref_str))
    st.markdown("##### Monthly sales evolution")
    v_filt["month"] = v_filt["fecha"].dt.to_period("M")
    ms = v_filt.groupby("month").agg(sales=("valores_h", "sum")).reset_index()
    ms["month_str"] = ms["month"].astype(str)
    ms["6-month rolling"] = ms["sales"].rolling(6, min_periods=1).mean()
    trend = ms[["month_str", "sales", "6-month rolling"]].rename(
        columns={"month_str": "Month", "sales": "Sales (€)"}).set_index("Month")
    st.line_chart(trend, height=300)

    st.markdown("---")

    # --- Priority alerts table ---
    st.markdown("##### Priority alerts")
    if len(alerts) > 0:
        f1, f2 = st.columns(2)
        cat_opts = sorted(alerts["category"].unique())
        cat_display = {
            "lost_client": "🔴 Lost client",
            "loss_risk": "🟠 Loss risk",
            "sales_opportunity": "🟡 Sales opportunity",
        }
        sel_cat = f1.multiselect("Category", cat_opts,
                                 default=["loss_risk", "lost_client"],
                                 format_func=lambda x: cat_display.get(x, x), key="fc")
        prio_opts = sorted(alerts["prioridad"].unique())
        sel_prio = f2.multiselect("Priority", prio_opts, default=prio_opts, key="fp")

        filtered = alerts[
            alerts["category"].isin(sel_cat) & alerts["prioridad"].isin(sel_prio)
        ]
        top_n = st.slider("Show top", 10, 100, 25, key="tn")
        display = filtered.head(top_n)[
            ["id_cliente", "provincia", "familia", "category",
             "prioridad", "contact_window_days", "motivo"]].copy()
        display["category"] = display["category"].map(lambda x: cat_display.get(x, x))
        display.columns = ["Client", "Prov.", "Family", "Category", "Prio.", "Days", "Motive"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        # Export buttons
        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button(
                "⬇️ Filtered alerts (CSV)",
                data=filtered.to_csv(index=False).encode("utf-8"),
                file_name=f"alerts_{ref_str}.csv",
                mime="text/csv",
            )
        with ex2:
            payloads = export_alerts(filtered.head(top_n), target="hubspot")
            st.download_button(
                "⬇️ Top-N as HubSpot Tasks (JSON)",
                data=json.dumps(payloads, indent=2, ensure_ascii=False).encode("utf-8"),
                file_name=f"alerts_hubspot_{ref_str}.json",
                mime="application/json",
            )


# ====================================================================
# TAB 3 — LEARNING LOOP
# ====================================================================
with tab_learning:
    st.markdown("### Outcome-driven feedback loop")
    st.warning(
        "⚠️ **Demo data — not real outcomes.** The 120 rows in `analysis/alert_outcomes.csv` are a "
        "calibrated simulation. In production these come from CRM webhooks, sales-team workflow tools, "
        "or a manual logging form. The schema, module, and dashboard are real; only the rows are illustrative.",
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
            st.markdown("##### Effectiveness by channel")
            bc = metrics["by_canal"].copy()
            bc["conversion_rate"]      = bc["conversion_rate"].map(lambda x: f"{x:.1%}")
            bc["revenue_captured_eur"] = bc["revenue_captured_eur"].map(lambda x: f"€{x:,.0f}")
            st.dataframe(bc, use_container_width=True, hide_index=True)
        with rr:
            st.markdown("##### Top false-positive reasons")
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


# ====================================================================
# Footer — architecture
# ====================================================================
st.markdown("---")
with st.expander("ℹ️ Architecture (data → analytical → activation → feedback)"):
    st.markdown("""
**Data layer** — cleaned CSVs in `std_data/csv/` (5 sheets: Ventas, Clientes, Productos, Potencial, Campañas)

**Analytical layer** — two segmentation modules:
- *Commodities* (anaesthesia, biosecurity): share-of-potential rule → loyal / promiscuous / marginal / churn_risk / lost
- *Technical* (biomaterials): individual-baseline rule with year-over-year comparison → systematic_active / silent / deterioration / occasional_* / lost

**Activation layer** — alert generator:
- `id_cliente × familia × tipo × motive × dynamic-window`
- `score = expected_impact × urgency × conversion_probability` (all four prioritisation signals from the brief)
- Routed to `delegado` / `televenta` / `marketing_automation`

**Feedback layer** — `alert_outcomes.csv` records action + result, fed back into:
- Conversion rate per `tipo_alerta` (precision)
- False-positive flagging
- Threshold-tuning recommendations

**Daily cadence** — `generate_alerts(as_of_date)` recomputes alerts for any date.
""")

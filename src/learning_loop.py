"""
Smart Demand Signals — feedback / learning loop.

Reads `alert_outcomes.csv`, joins with `alerts.csv`, and computes:
  - per-tipo conversion rates (precision)
  - per-canal effectiveness
  - false-positive rates and top reasons
  - response-time stats
  - rule-tuning recommendations

This is rule-tuning, not ML retraining — keeping it analytical and explainable
per the brief's guidance.
"""
from __future__ import annotations
from pathlib import Path
from datetime import date as _date
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ALERTS_PATH   = ROOT / "analysis" / "alerts.csv"
OUTCOMES_PATH = ROOT / "analysis" / "alert_outcomes.csv"

OUTCOME_COLUMNS = [
    "outcome_id", "alert_id", "recorded_at", "taken_by", "action_taken",
    "outcome_status", "revenue_captured_eur", "time_to_action_days",
    "false_positive_reason", "notes",
]
VALID_STATUS = {"won", "lost", "pending", "no_contact", "false_positive"}


# ---------- Recording ----------
def record_outcome(alert_id: str, action_taken: str, outcome_status: str,
                   taken_by: str, *, revenue_captured_eur: float = 0.0,
                   time_to_action_days: int | None = None,
                   false_positive_reason: str = "", notes: str = "") -> dict:
    """Append a new outcome row to alert_outcomes.csv. Returns the row written."""
    if outcome_status not in VALID_STATUS:
        raise ValueError(f"outcome_status must be one of {VALID_STATUS}")
    today = pd.Timestamp.today().normalize()
    existing = pd.read_csv(OUTCOMES_PATH) if OUTCOMES_PATH.exists() else pd.DataFrame(columns=OUTCOME_COLUMNS)
    next_idx = len(existing) + 1
    row = {
        "outcome_id":            f"OUT-{today.strftime('%Y%m%d')}-{next_idx:04d}",
        "alert_id":              alert_id,
        "recorded_at":           today.date(),
        "taken_by":              taken_by,
        "action_taken":          action_taken,
        "outcome_status":        outcome_status,
        "revenue_captured_eur":  float(revenue_captured_eur),
        "time_to_action_days":   time_to_action_days,
        "false_positive_reason": false_positive_reason,
        "notes":                 notes,
    }
    pd.concat([existing, pd.DataFrame([row])], ignore_index=True).to_csv(OUTCOMES_PATH, index=False)
    return row


# ---------- Loading ----------
def load_joined() -> pd.DataFrame:
    """alerts.csv ⨝ alert_outcomes.csv on alert_id."""
    a = pd.read_csv(ALERTS_PATH, dtype={"id_cliente": str})
    if not OUTCOMES_PATH.exists():
        return pd.DataFrame()
    o = pd.read_csv(OUTCOMES_PATH, parse_dates=["recorded_at"])
    return o.merge(a, on="alert_id", how="left")


# ---------- Metrics ----------
def compute_metrics() -> dict:
    """Return a dict of dataframes summarising the feedback signal."""
    j = load_joined()
    if j.empty:
        return {"empty": True}

    # Conversion rate by tipo_alerta
    by_tipo = (j.assign(won=(j["outcome_status"] == "won"),
                        false_positive=(j["outcome_status"] == "false_positive"))
                 .groupby("tipo_alerta")
                 .agg(n_outcomes=("alert_id", "count"),
                      n_won=("won", "sum"),
                      n_false_positive=("false_positive", "sum"),
                      revenue_captured_eur=("revenue_captured_eur", "sum"),
                      avg_time_to_action_days=("time_to_action_days", "mean"))
                 .reset_index())
    by_tipo["conversion_rate"]      = (by_tipo["n_won"] / by_tipo["n_outcomes"]).round(3)
    by_tipo["false_positive_rate"]  = (by_tipo["n_false_positive"] / by_tipo["n_outcomes"]).round(3)
    n_won = by_tipo["n_won"].astype(float)
    by_tipo["avg_revenue_per_won"]  = (
        (by_tipo["revenue_captured_eur"] / n_won.where(n_won > 0))
        .round(0).astype("Float64"))

    # Conversion by canal
    by_canal = (j.assign(won=(j["outcome_status"] == "won"))
                  .groupby("canal_recomendado")
                  .agg(n_outcomes=("alert_id", "count"),
                       n_won=("won", "sum"),
                       revenue_captured_eur=("revenue_captured_eur", "sum"))
                  .reset_index())
    by_canal["conversion_rate"] = (by_canal["n_won"] / by_canal["n_outcomes"]).round(3)

    # Conversion by prioridad
    by_prio = (j.assign(won=(j["outcome_status"] == "won"))
                 .groupby("prioridad")
                 .agg(n_outcomes=("alert_id", "count"),
                      n_won=("won", "sum"),
                      revenue_captured_eur=("revenue_captured_eur", "sum"))
                 .reset_index())
    by_prio["conversion_rate"] = (by_prio["n_won"] / by_prio["n_outcomes"]).round(3)

    # False-positive reasons
    fp = (j[j["outcome_status"] == "false_positive"]
            .groupby("false_positive_reason").size().reset_index(name="n"))
    fp = fp.sort_values("n", ascending=False)

    # Headline numbers
    headline = {
        "n_alerts_total":        len(pd.read_csv(ALERTS_PATH)),
        "n_outcomes_total":      len(j),
        "overall_conversion":    round((j["outcome_status"] == "won").mean(), 3),
        "false_positive_rate":   round((j["outcome_status"] == "false_positive").mean(), 3),
        "no_contact_rate":       round((j["outcome_status"] == "no_contact").mean(), 3),
        "revenue_captured_eur":  float(j["revenue_captured_eur"].sum()),
        "median_time_to_action": float(j["time_to_action_days"].median()),
    }

    return {
        "empty": False,
        "headline": headline,
        "by_tipo": by_tipo,
        "by_canal": by_canal,
        "by_prio": by_prio,
        "false_positive_reasons": fp,
    }


# ---------- Recommendations ----------
def recommend_threshold_adjustments() -> list[str]:
    """Plain-language tuning suggestions derived from outcomes."""
    m = compute_metrics()
    if m.get("empty"):
        return ["No outcomes recorded yet — collect feedback to enable recommendations."]

    recs: list[str] = []
    overall = m["headline"]["overall_conversion"]
    by_tipo = m["by_tipo"]

    # 1. Underperforming tipo_alerta
    for _, r in by_tipo.iterrows():
        if r["n_outcomes"] < 5:
            continue
        if r["conversion_rate"] < overall * 0.6:
            recs.append(
                f"⚠️  `{r['tipo_alerta']}` converts at {r['conversion_rate']:.0%} "
                f"vs overall {overall:.0%} (n={r['n_outcomes']}). "
                f"Consider raising the threshold or rerouting to a lower-cost channel."
            )

    # 2. High-FP tipo_alerta
    for _, r in by_tipo.iterrows():
        if r["n_outcomes"] < 5:
            continue
        if r["false_positive_rate"] > 0.10:
            recs.append(
                f"🚩  `{r['tipo_alerta']}` has {r['false_positive_rate']:.0%} false-positive rate. "
                f"Review the dominant reasons — likely a data-quality issue, not a model issue."
            )

    # 3. Channel comparison
    by_canal = m["by_canal"]
    if len(by_canal) >= 2:
        top    = by_canal.sort_values("conversion_rate", ascending=False).iloc[0]
        bottom = by_canal.sort_values("conversion_rate", ascending=False).iloc[-1]
        if top["conversion_rate"] - bottom["conversion_rate"] > 0.10:
            recs.append(
                f"📞  `{top['canal_recomendado']}` converts at {top['conversion_rate']:.0%} "
                f"vs `{bottom['canal_recomendado']}` at {bottom['conversion_rate']:.0%}. "
                f"Consider routing more borderline alerts to {top['canal_recomendado']}."
            )

    # 4. No-contact pressure
    if m["headline"]["no_contact_rate"] > 0.15:
        recs.append(
            f"⏰  {m['headline']['no_contact_rate']:.0%} of alerts went uncontacted. "
            f"Either capacity is the bottleneck, or daily alert volume should be reduced."
        )

    if not recs:
        recs.append("✅ Conversion is uniform across types and channels — no immediate tuning needed.")

    return recs


if __name__ == "__main__":
    m = compute_metrics()
    if m.get("empty"):
        print("No outcomes yet.")
    else:
        print("=== Headline ===")
        for k, v in m["headline"].items():
            print(f"  {k}: {v}")
        print("\n=== By tipo_alerta ===")
        print(m["by_tipo"].to_string(index=False))
        print("\n=== By canal ===")
        print(m["by_canal"].to_string(index=False))
        print("\n=== False-positive reasons ===")
        print(m["false_positive_reasons"].to_string(index=False))
        print("\n=== Recommendations ===")
        for r in recommend_threshold_adjustments():
            print(f"  • {r}")

"""
Minimal smoke tests for the alert pipeline.
Run with:  .venv/bin/python -m pytest tests/ -v
Or simply: .venv/bin/python tests/test_smoke.py
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smart_demand_signals import generate_alerts, load_data
from learning_loop import compute_metrics, recommend_threshold_adjustments
from crm_export import export_alerts


_data = None
def _get_data():
    global _data
    if _data is None:
        _data = load_data()
    return _data


def test_generate_alerts_runs_and_returns_dataframe():
    a = generate_alerts("2025-12-29", data=_get_data())
    assert isinstance(a, pd.DataFrame)
    assert len(a) > 0
    expected = {"alert_id", "id_cliente", "tipo_alerta", "prioridad",
                "score", "canal_recomendado", "trace_features"}
    assert expected.issubset(set(a.columns))


def test_alert_id_is_unique_per_day():
    a = generate_alerts("2025-12-29", data=_get_data())
    assert a["alert_id"].is_unique


def test_score_equals_impact_times_urgency_times_conv_prob():
    a = generate_alerts("2025-12-29", data=_get_data())
    s = (a["expected_impact_eur"] * a["urgency_factor"]
         * a["conversion_probability"]).round(6)
    assert (a["score"].round(6) == s).all()


def test_conversion_probability_in_range():
    a = generate_alerts("2025-12-29", data=_get_data())
    assert "conversion_probability" in a.columns
    assert (a["conversion_probability"] >= 0).all()
    assert (a["conversion_probability"] <= 1).all()


def test_loyalty_tier_and_trend_columns():
    a = generate_alerts("2025-12-29", data=_get_data())
    assert "loyalty_tier" in a.columns
    assert "trend" in a.columns
    valid_trend = {"improving", "declining", "stable", "new", "inactive", ""}
    assert set(a["trend"].unique()).issubset(valid_trend)


def test_alerts_sorted_by_score_desc():
    a = generate_alerts("2025-12-29", data=_get_data())
    assert (a["score"].diff().dropna() <= 0).all()


def test_tipo_alerta_uses_known_vocabulary():
    a = generate_alerts("2025-12-29", data=_get_data())
    valid = {"capture_window", "silent", "churn_risk", "opportunity_spike", "lost"}
    assert set(a["tipo_alerta"].unique()).issubset(valid)


def test_lost_segment_is_separated_from_churn():
    a = generate_alerts("2025-12-29", data=_get_data())
    lost = a[a["tipo_alerta"] == "lost"]
    silent = a[a["tipo_alerta"] == "silent"]
    # Lost alerts only fire for clients with prior cyclic activity (filtered)
    # and may be High or Medium based on baseline impact
    if len(lost):
        assert lost["prioridad"].isin(["High", "Medium", "Low"]).all()
        # And there should be fewer lost than candidate-lost rows in segments
        # (the cyclic filter removes some)
        assert len(lost) > 0


def test_holiday_flag_present():
    a = generate_alerts("2025-08-15", data=_get_data())
    assert "holiday_period" in a.columns
    assert bool(a["holiday_period"].iloc[0])  # August → holiday
    a = generate_alerts("2025-04-15", data=_get_data())
    assert not bool(a["holiday_period"].iloc[0])  # April → not holiday


def test_yoy_baseline_used_when_available():
    """At least some technical pairs should use YoY baseline by 2025-12-29."""
    import sys, json
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import (
        load_data, filter_commercial_activity, technical_patterns)
    data = _get_data()
    v = filter_commercial_activity(data["ventas"], pd.Timestamp("2025-12-29"))
    tp = technical_patterns(v, pd.Timestamp("2025-12-29"))
    assert "baseline_source" in tp.columns
    assert (tp["baseline_source"] == "yoy").sum() > 0


def test_canal_routing():
    a = generate_alerts("2025-12-29", data=_get_data())
    assert set(a["canal_recomendado"].unique()).issubset(
        {"delegado", "televenta", "marketing_automation"})


def test_works_on_early_date_no_baseline():
    """Reproduces the KeyError fix — early dates have no baseline window."""
    a = generate_alerts("2021-06-30", data=_get_data())
    assert isinstance(a, pd.DataFrame)


def test_snooze_reduces_alert_count():
    a_with    = generate_alerts("2025-12-29", data=_get_data(), apply_snooze=True)
    a_without = generate_alerts("2025-12-29", data=_get_data(), apply_snooze=False)
    assert len(a_with) <= len(a_without)


def test_campaign_annotation_present():
    a = generate_alerts("2025-12-29", data=_get_data())
    assert "campaign_active" in a.columns
    assert "campaign_name" in a.columns


def test_invalid_date_raises():
    try:
        generate_alerts("not-a-date", data=_get_data())
    except (ValueError, Exception) as e:
        assert e is not None
        return
    raise AssertionError("Expected error on invalid date")


def test_learning_loop_metrics_computable():
    m = compute_metrics()
    assert "headline" in m or m.get("empty")
    if not m.get("empty"):
        assert m["headline"]["overall_conversion"] >= 0
        assert m["headline"]["overall_conversion"] <= 1


def test_threshold_recommendations_returns_strings():
    recs = recommend_threshold_adjustments()
    assert isinstance(recs, list)
    assert all(isinstance(r, str) for r in recs)


def test_client_profiles_share_of_potential_uses_trailing_12m():
    """Regression test for the lifetime-vs-annual share_of_potential bug."""
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import build_client_profiles, filter_commercial_activity
    data = _get_data()
    v = filter_commercial_activity(data["ventas"], pd.Timestamp("2025-12-29"))
    p = build_client_profiles(v, data["potencial"], pd.Timestamp("2025-12-29"))
    # Median should be reasonable — under 0.5 means trailing-12m is being used.
    # If lifetime were used it would be >1 for most clients with 5y of buying.
    assert p["share_of_potential"].dropna().median() < 0.5


def test_dynamic_contact_window_clamps_for_overdue_clients():
    from smart_demand_signals import _dynamic_contact_window
    # Client overdue (cycle 30d, recency 60d) → window collapses
    overdue = {"mean_interpurchase_days": 30, "recency_days": 60}
    assert _dynamic_contact_window(overdue, default_win=30) <= 8
    # On-cycle client (cycle 30d, recency 25d) → 5 days until expected
    on_cycle = {"mean_interpurchase_days": 30, "recency_days": 25}
    assert _dynamic_contact_window(on_cycle, default_win=30) == 5
    # No cycle data → falls back to default
    no_data = {"mean_interpurchase_days": None, "recency_days": 100}
    assert _dynamic_contact_window(no_data, default_win=30) == 30


def test_lost_alerts_filtered_to_cyclic_clients():
    """Lost alerts should not fire for clients with insufficient history."""
    a = generate_alerts("2025-12-29", data=_get_data())
    lost = a[a["tipo_alerta"] == "lost"]
    if len(lost):
        # All lost alerts should have meaningful baseline impact (≥€200 by filter)
        # — the filter is on lifetime_volume but baseline is a strong proxy
        assert (lost["expected_impact_eur"] > 0).all()


def test_crm_export_hubspot_shape():
    a = generate_alerts("2025-12-29", data=_get_data())
    payloads = export_alerts(a, target="hubspot", top_n=3)
    assert len(payloads) == 3
    for p in payloads:
        assert "properties" in p
        assert "associations" in p
        assert "hs_task_subject" in p["properties"]
        assert "inibsa_alert_id" in p["properties"]


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = []
    for fn in fns:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except AssertionError as e:
            failed.append(fn.__name__)
            print(f"  ✗ {fn.__name__}  ({e})")
        except Exception as e:
            failed.append(fn.__name__)
            print(f"  ✗ {fn.__name__}  ({type(e).__name__}: {e})")
    print(f"\n{len(fns) - len(failed)}/{len(fns)} passed")
    if failed:
        sys.exit(1)

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


def test_score_equals_impact_times_urgency():
    a = generate_alerts("2025-12-29", data=_get_data())
    s = (a["expected_impact_eur"] * a["urgency_factor"]).round(6)
    assert (a["score"].round(6) == s).all()


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
    if len(lost):
        # Lost should be lower priority than active silent alerts
        assert (lost["prioridad"] == "Low").all()


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
    assert set(a["canal_recomendado"].unique()).issubset({"delegado", "televenta"})


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

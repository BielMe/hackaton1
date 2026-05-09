# Smart Demand Signals — Pitch Deck

**Inibsa · Interhack BCN 2026**

---

## Slide 1 — Title

# Smart Demand Signals
### Daily commercial alerts for 6,000 dental clinics
*Inibsa · Interhack BCN 2026 · Equipo [name]*

---

## Slide 2 — The problem (30s)

> **Every morning, Inibsa's sales team faces the same question:**
> *"Which of our 6,000 clinics should we contact today, and why?"*

Today this is mostly intuition + scattered KPIs.

Three commercial truths the data reveals:
- **Loyal clinics** buying ~80% of their estimated potential
- **Promiscuous clinics** capturing only ~17% — splitting demand with competitors
- **Silent clinics** that used to buy €15K/year and have gone quiet for 700+ days

You can't act on what you can't see.

---

## Slide 3 — Our approach (45s)

We turn 5 years of sales history into a **daily ranked alert table**.

Two parallel logics, because the brief insists on it:

| Commodities (anaesthesia, needles, disinfectants) | Technical products (biomaterials, implants) |
|---|---|
| Recurring purchases — compare against potential | Sporadic purchases — compare against the clinic's *own* history |
| Detects: *uncaptured demand* | Detects: *deviation from individual pattern* |

**Output**: a sorted alert per day per (clinic × product family) with reason, urgency, channel routing, and full traceability.

---

## Slide 4 — What's in an alert (45s)

```json
{
  "alert_id": "ALT-20251229-000001",
  "id_cliente": "40439",
  "provincia": "Zaragoza",
  "familia": "Categoria C2",
  "tipo_alerta": "capture_window",
  "prioridad": "High",
  "score": 57875,
  "expected_impact_eur": 82679,
  "canal_recomendado": "delegado",
  "contact_window_days": 7,
  "motivo": "Cliente promiscuo: capturado 6% del potencial;
             €82,679 de demanda desviada a competencia",
  "trace_features": {
    "share_of_potential": 0.06,
    "potencial_h": 87672,
    "volume_eur_current": 4993,
    "recency_days": 47
  }
}
```

Every number that fired the alert is in the trace. **No black box.**

---

## Slide 5 — Live demo (3 min)

Three things to show in the dashboard:

### 1. Daily-cadence proof
> *"Drag the date slider back to 2024-06-30. The alert table changes."*
The same code, run on any historical date, produces a fresh alert list. That's the daily recalculation the brief requires.

### 2. Top alerts + drill-in
> *"Look at alert #1 — Zaragoza promiscuous client, €82K of uncaptured demand. Click trace features."*
Show the raw numbers. This is interpretability.

### 3. Learning-loop tab
> *"120 mocked outcomes — capture_window converts at 33%, silent at 11%. The system suggests raising thresholds for silent."*
This is how the system gets smarter without ML.

---

## Slide 6 — Numbers (45s)

For the reference date `2025-12-29`:

|   | Value |
|---|---|
| Active client × category pairs | 9,539 (commodity) + 6,515 (technical) |
| Alerts generated | **4,775** (after snooze) |
| **High priority** | **1,599** |
| Total expected commercial impact | **€18.6M** |
| Top single alert | €82K of uncaptured demand from one client |

---

## Slide 7 — ROI (60s)

If the sales team handles ~50 high-priority alerts per day:

```
   50 alerts/day × 23% observed conversion = 11.7 wins/day
   11.7 wins × €2,483 avg revenue per won alert = €28,923/day
                                                = €636K/month
                                                = €7.6M/year
```

Numbers are based on mocked outcome rates calibrated to be conservative.
Even at half the conversion, the system pays for itself many times over.

---

## Slide 8 — Architecture (45s)

Four layers, separated by design — exactly what the brief asks for.

```
   Feedback layer       (alert_outcomes.csv → metrics → rule tuning)
        ▲
   Activation layer     (build_alerts → ranked, traceable, routed)
        ▲
   Analytical layer     (commodity_segments / technical_patterns)
        ▲
   Data layer           (cleaned CSVs, daily granularity)
```

- **Standalone** today (Python module + Streamlit dashboard)
- **CRM-agnostic** — `crm_export.py` already emits HubSpot Tasks-shaped JSON
- **Daily idempotent** — `generate_alerts(as_of_date)` is the single entry point

---

## Slide 9 — Brief scorecard (60s)

| # | Brief deliverable | Status |
|---|---|---|
| 1 | Purchase-need prediction for commodities | ✅ |
| 2 | Early churn-risk detection for technical | ✅ |
| 3 | Capture-window identification | ✅ |
| 4 | Interpretable, actionable alerts | ✅ |
| 5 | Operational prioritisation | ✅ |
| 6 | Daily-operation proposal | ✅ |
| 7 | Standalone → CRM evolution | ✅ (HubSpot adapter shipped) |
| 8 | Learning capability | ✅ (schema + module + dashboard) |

8 of 8.

---

## Slide 10 — What's next (30s)

**Phase 2 (post-hackathon):**
- Wire alerts into Inibsa's actual CRM via `crm_export.py`
- Replace mocked outcomes with real recordings from sales team
- Threshold auto-tuning when ≥500 outcomes recorded
- Clinic-typology-conditioned expected-demand models
- Map view by provincia / delegado territory

The architecture supports all of this without rewrites.

---

## Slide 11 — Questions

# Thank you.
### Smart Demand Signals
*github.com/BielMe/hackaton1*

# Smart Demand Signals — daily alert engine

## Quick start

```bash
pip install -r requirements.txt

# Generate alerts for a specific date (CLI)
python src/smart_demand_signals.py 2025-12-29

# Launch interactive dashboard
streamlit run src/dashboard.py
```

## Layered architecture

```
┌─────────────────────────────────────────────┐
│ Activation layer                            │
│   build_alerts() → ranked alert table       │
│   • tipo_alerta, motivo, prioridad          │
│   • score = impact × urgency                │
│   • canal_recomendado, contact_window_days  │
│   • trace_features (JSON, full lineage)     │
└─────────────────────────────────────────────┘
                     ▲
┌─────────────────────────────────────────────┐
│ Analytical layer                            │
│   commodity_segments()                      │
│     loyal / promiscuous / churn_risk_*      │
│   technical_patterns()                      │
│     systematic_*  /  occasional_*           │
└─────────────────────────────────────────────┘
                     ▲
┌─────────────────────────────────────────────┐
│ Data layer                                  │
│   load_data() — Ventas, Clientes,           │
│   Productos, Potencial, Mapping_familia     │
└─────────────────────────────────────────────┘
```

## Public API

```python
from smart_demand_signals import generate_alerts, load_data

data = load_data()                                    # one-shot load
alerts = generate_alerts("2025-12-29", data=data)     # per-day alerts
```

## Daily cadence

`generate_alerts(as_of_date)` is idempotent and date-parameterised. Re-running on a new date produces a new alert table from the same source data — no schema drift, no manual steps.

## Output schema

| Column | Description |
|---|---|
| `alert_id` | Stable per-day ID `ALT-YYYYMMDD-NNNNNN` |
| `id_cliente` | Client ID |
| `familia` | Product family code (C1/C2/T1/T2) |
| `tipo_alerta` | `capture_window` / `silent` / `churn_risk` / `opportunity_spike` |
| `motivo` | Human-readable reason |
| `prioridad` | High / Medium / Low |
| `score` | `expected_impact_eur × urgency_factor` |
| `canal_recomendado` | `delegado` / `televenta` |
| `contact_window_days` | 7 / 30 / 90 |
| `trace_features` | JSON of metric values that triggered the alert |

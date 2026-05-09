"""
CRM export — convert internal alert rows to CRM-friendly JSON payloads.

The system itself stays CRM-agnostic. This module is a thin adapter that
shows the standalone-to-CRM evolution path the brief asks for.

Currently supports two output shapes:
  - HubSpot Engagements (Tasks API)
  - Salesforce Lead/Task (generic shape — adapter only)

In production, an outbound webhook or scheduled job would call
`emit_hubspot_task()` per alert and POST to the HubSpot Tasks API.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def emit_hubspot_task(alert: dict) -> dict:
    """
    Convert one alert row (as a dict) into a HubSpot Engagements Tasks payload.

    Reference: https://developers.hubspot.com/docs/api/crm/engagements/tasks
    """
    fecha = pd.Timestamp(alert["fecha_alerta"])
    due_dt = fecha + timedelta(days=int(alert["contact_window_days"]))
    return {
        "properties": {
            "hs_task_subject": f"[{alert['prioridad']}] {alert['tipo_alerta']} — Cliente {alert['id_cliente']}",
            "hs_task_body":   alert["motivo"],
            "hs_task_status": "NOT_STARTED",
            "hs_task_priority": {"High": "HIGH", "Medium": "MEDIUM", "Low": "LOW"}[alert["prioridad"]],
            "hs_task_type":   "CALL" if alert["canal_recomendado"] == "televenta" else "MEETING",
            "hs_timestamp":   int(due_dt.replace(tzinfo=timezone.utc).timestamp() * 1000),
            # Custom fields the Inibsa team would create on the Task object:
            "inibsa_alert_id":             alert["alert_id"],
            "inibsa_score":                float(alert["score"]),
            "inibsa_expected_impact_eur":  float(alert["expected_impact_eur"]),
            "inibsa_familia":              alert["familia"],
            "inibsa_canal":                alert["canal_recomendado"],
            "inibsa_clinic_typology":      alert.get("clinic_typology", ""),
            "inibsa_campaign_active":      bool(alert.get("campaign_active", False)),
            "inibsa_trace_features":       alert["trace_features"],
        },
        "associations": [
            {
                "to": {"idProperty": "external_id", "id": alert["id_cliente"]},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 204  # Task → Contact
                }]
            }
        ]
    }


def emit_salesforce_task(alert: dict) -> dict:
    """Generic Salesforce Task shape (illustrative)."""
    fecha = pd.Timestamp(alert["fecha_alerta"])
    due_date = (fecha + timedelta(days=int(alert["contact_window_days"]))).date().isoformat()
    return {
        "Subject":     f"[{alert['prioridad']}] {alert['tipo_alerta']} — Cliente {alert['id_cliente']}",
        "Description": alert["motivo"],
        "Priority":    alert["prioridad"],
        "Status":      "Not Started",
        "ActivityDate": due_date,
        "Type":        "Call" if alert["canal_recomendado"] == "televenta" else "Visit",
        "Inibsa_Alert_Id__c":            alert["alert_id"],
        "Inibsa_Score__c":               float(alert["score"]),
        "Inibsa_Expected_Impact_Eur__c": float(alert["expected_impact_eur"]),
        "Inibsa_Familia__c":             alert["familia"],
        "Inibsa_Trace_Features__c":      alert["trace_features"],
        "WhoId_External":                alert["id_cliente"],
    }


def export_alerts(alerts: pd.DataFrame, target: str = "hubspot",
                  top_n: int | None = None) -> list[dict]:
    """
    Convert an alert DataFrame to a list of CRM-shaped dicts.

    target  : 'hubspot' or 'salesforce'
    top_n   : if given, only export the highest-scoring N alerts
    """
    rows = alerts.head(top_n) if top_n else alerts
    emit = {"hubspot": emit_hubspot_task, "salesforce": emit_salesforce_task}[target]
    return [emit(r.to_dict()) for _, r in rows.iterrows()]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from smart_demand_signals import generate_alerts

    alerts = generate_alerts("2025-12-29")
    payloads = export_alerts(alerts, target="hubspot", top_n=3)
    print(json.dumps(payloads, indent=2, ensure_ascii=False))

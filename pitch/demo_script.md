# Demo Script — 3-minute walkthrough

Practice once. Three minutes is tight. Speak in cuttable sentences.

---

## 0. Setup before stepping on stage (≤30s)

```bash
cd /Users/suli/GitHub/interhack
.venv/bin/streamlit run src/dashboard.py
```

Open browser at `http://localhost:8501`. **Set the date picker to `2025-12-29` (default).**

Have the **Alerts** tab visible.

---

## 1. The problem framing (30s)

> *"Inibsa serves 6,000 dental clinics. Every morning the sales team has to figure out who to call. Today this is mostly intuition. We turned five years of sales history into a daily ranked call list — and importantly, we treat **commodities** and **technical products** with two completely different logics, because the brief is explicit about that."*

Point at the **Total alerts: 4,775** card.
Point at **High priority: 1,599** card.
Point at **Expected impact: €18.6M** card.

> *"4,775 alerts firing today, 1,600 of them high priority, totalling €18.6 million of commercial value at stake."*

---

## 2. The daily cadence (30s)

Grab the **date picker** in the sidebar. Drag it back to **2024-06-30**.

> *"This is the same system, running for any historical date. The alert list changes because the windows shift. That's the daily-recalculation requirement, demonstrated live."*

Drag back to **2025-12-29**.

---

## 3. The top alert (45s)

Scroll to the top of the alerts table. Point at row 1 — Zaragoza, promiscuous, €82K.

> *"Top alert: a clinic in Zaragoza that's only capturing 6% of their potential — €82,000 of uncaptured demand. They're an active customer, not silent. They just buy most of their stuff somewhere else."*

Scroll to **Drill into a single alert**. Pick `ALT-20251229-000001`.

> *"Every alert is traceable. Here's the raw numbers: their potential is €88K, they bought €5K, last purchase 47 days ago, share-of-potential 6%. No black box."*

Point at the **Trace features** JSON.

---

## 4. The two logics (30s)

Filter sidebar: tick only **`Productos Técnicos`** in Bloque analítico.

> *"For technical products, the share-of-potential approach doesn't work — these are sporadic. So we compare each clinic against its own historical pattern. A clinic that used to buy every 60 days and is now silent for 700 days is a churn-risk; a clinic that buys once a year is normal."*

Untick filter back to default.

---

## 5. Learning loop tab (45s)

Click the **📈 Learning loop** tab.

> *"This is the feedback loop. Right now it's seeded with 120 mocked outcomes — clearly labelled — but the schema is real and so is the module. In production these would come from the CRM."*

Point at the **Conversion by alert type** table.

> *"Capture-window alerts convert at 33%, silent alerts at only 11%. The system flags this and recommends raising thresholds for silent."*

Scroll to **Recommended threshold adjustments**. Read the recommendation aloud.

---

## 6. Closing (15s)

Switch back to **Alerts** tab. Click **⬇️ Export top-N as HubSpot Tasks (JSON)**.

> *"And when Inibsa is ready to wire this into HubSpot, the export endpoint already produces the right payload shape. Standalone today, CRM-ready tomorrow."*

> *"4,775 alerts a day, full traceability, learning loop, CRM adapter — eight out of eight on the brief's deliverables."*

**Thank you.**

---

## Backup answers (if asked)

**Q: "Why these specific thresholds?"**
*A:* "They're business heuristics. The Learning loop tab shows their conversion rates — when we have enough real outcomes, the threshold-tuning module will adjust them automatically. We also computed the data-driven quartile alternatives in `analysis/thresholds.json`."

**Q: "What about clients without potential data?"**
*A:* "Briefing flags that 16% of `potencial_h` rows are zero or unknown. We segment those as `unknown_potential` rather than guessing — they get reviewed separately."

**Q: "Won't this fire the same silent alert every day?"**
*A:* "No — when an outcome is recorded as won, lost, or false_positive, that (client × familia × tipo) is snoozed for 30 days. See `snooze_recently_actioned()` in `smart_demand_signals.py`."

**Q: "Is this ML?"**
*A:* "Deliberately not — the brief is explicit that the key is analytical and commercial utility, not technical sophistication. We use rule-based detection with a feedback loop that tunes thresholds. Easy for the commercial team to interpret, easy for IT to maintain."

**Q: "How does it scale?"**
*A:* "Daily run takes ~5 seconds for 6,000 clients. Linear in client count. The architecture is layered: data / analytical / activation / feedback. Swap any layer without touching the others."

**Q: "What about Portugal?"**
*A:* "Briefing said Portugal data quality is lower so the initial scope is Spain only. The pipeline is country-agnostic — adding Portugal is a data-source change, not a code change."

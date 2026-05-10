# Demo walkthrough — 3 minutes

**Goal:** show a working daily alert engine for Inibsa's 6,000 dental clinics, end-to-end, in three minutes. The dashboard does the talking — slides bookend it.

**Pre-flight:**
```bash
.venv/bin/streamlit run src/dashboard.py
```
Open `http://localhost:8501`. Make sure:
- Date picker is set to **2025-12-29**
- You're on the **Client view** tab
- A high-score client is pre-selected (top of dropdown)

---

## Beat 1 — Client view (60 seconds)

**🕒 0:00 — 1:00**
**👀 Show:** Client view tab, top client.

**🎤 Say:**
> "This is a working call list for Inibsa's sales team. Every morning the system asks: *which of our 6,000 clinics should we contact today, and why?*"

(Point at the orange banner.)

> "This client is flagged **Loss Risk**. The system tells the rep what to do — *Urgent visit or call, contact within 7 days* — and gives the reason: *loyal client, used to buy €X a year, no purchase for 180 days.*"

(Point at the cycle-status pill.)

> "Crucial detail: cycle status is **Overdue** — they're 26% past their normal purchase cycle. We're not flagging absolute silence, we're flagging *abnormal* silence for **this specific client**. Each clinic gets compared to its own pattern."

(Point at the purchase-history line chart.)

> "And here's the visible drop in the chart."

---

## Beat 2 — Monitoring + daily cadence (75 seconds)

**🕒 1:00 — 2:15**
**👀 Show:** Switch to the **Monitoring** tab.

**🎤 Say:**
> "Switching to monitoring. KPI strip at the top: 4,271 alerts total, split into four sales-team-readable categories — lost clients, loss risk, opportunities, healthy."

(Drag the date picker back to **2024-06-30**.)

> "Now the **daily-cadence proof**: same code, **18 months earlier**. The alert table updates instantly. Different clients in trouble back then. The system is **idempotent** — it works for any historical date, no leakage."

(Drag back to **2025-12-29**.)

(Point at the bar chart by category.)

> "Charts: most alerts are *sales opportunities* and *loss risk* — the actionable ones. **Marketing automation** absorbs the low-priority alerts, freeing up the sales reps."

(Scroll to the priority-alerts table at the bottom; click **⬇️ Top-N as HubSpot Tasks (JSON)**.)

> "And when Inibsa wires this into HubSpot, the export already produces the right payload shape. **Standalone today, CRM-ready tomorrow.**"

---

## Beat 3 — Learning loop (45 seconds)

**🕒 2:15 — 3:00**
**👀 Show:** Click the **Learning loop** tab.

**🎤 Say:**
> "Final piece — the feedback loop. **Disclaimer up top: this is mocked demo data**, clearly labelled. Real outcomes flow in from the CRM."

(Point at the conversion-by-type table.)

> "Capture-window alerts convert at **33%**. Silent alerts at **11%**. The system already shows which alert types pull their weight — and which need threshold tuning."

(Scroll to **Recommended threshold adjustments**.)

> "And below: **automatic suggestions**. *'Silent alerts converting at 11% versus average 23% — consider raising the threshold.'* When real outcomes accumulate, the system tunes its own rules. **No retraining. No black box.**"

---

## Wrap (return to slide 3)

**🎤 Say:**
> "Eight of eight brief deliverables, all four prioritisation signals, full traceability on every alert. Thank you — happy to take questions."

---

## Backup answers (Q&A)

**"How do you measure accuracy?"**
> "Predictive accuracy needs a controlled pilot — that's phase 2. Today we defend the **logic**: every threshold is documented, every alert is traceable, every multiplier has a rationale."

**"Why these specific thresholds?"**
> "Heuristics calibrated to the brief's segments. The Learning loop tab shows which ones convert — when we have ≥500 real outcomes, the threshold-tuning module adjusts them."

**"Won't the same silent alert fire every day?"**
> "No. Once a sales rep records an outcome (won, lost, or false-positive), that combination of client × family × type is **snoozed for 30 days**."

**"Is this Machine Learning?"**
> "Deliberately not. The brief is explicit: *the key is analytical and commercial utility, not technical sophistication.* We use rules with a feedback loop. ML becomes a real option once we have ≥500 labelled outcomes — until then, training would be self-deception."

**"What about the August drop?"**
> "Empirically measured: August is 25-38% of the yearly average for our families. Without seasonality awareness, the system would fire ~1,500 false-positive churn alerts every August. We use a **year-over-year baseline** and a **holiday flag** — drop signals during August are suppressed unless YoY also shows a real decline."

---

## Stage cheat sheet

| If… | Do this |
|---|---|
| Demo crashes | Switch to slide 3 — it tells the same story numerically |
| Running over 3 min | Cut Beat 3 (learning loop) — say "we also have a feedback loop, feel free to ask" |
| Running under | Pick another client in Beat 1 with a different category to show variety |
| Judge interrupts with a question | Answer briefly, return to where you were — don't restart the beat |
| Network issue | All data is local — no internet needed |

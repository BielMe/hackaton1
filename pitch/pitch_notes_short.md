# Pitch notes — 3-slide deck (Inibsa Alert Marker)

**Total target time:** ~2 minutes for the slide portion.
**File:** `pitch/Inibsa_Alert_Marker_short.pptx`
**Demo guide for the additional 3 minutes:** `pitch/demo_walkthrough_3min.md`

Each slide below has:
- **🕒** target time
- **👀** what to point at
- **🎤** word-for-word talk track

---

## Slide 1 — Cover (Mythos / Inibsa Alert Marker)

**🕒 Time:** 10 seconds.
**👀 Show:** Stand still. Let the slide speak — no need to point.

**🎤 Say:**
> "Hi, we're Mythos Group. This is **Inibsa Alert Marker** — a daily commercial-alert engine for Inibsa's six thousand dental clinics."

(Move to slide 2.)

---

## Slide 2 — Opportunity + Approach

**🕒 Time:** 50 seconds.
**👀 Show:** Point at the title, then at the **left card**, then at the **right card**, then at the footer line.

**🎤 Say:**
> "Inibsa sells to roughly six thousand clinics across Spain. Every morning, the sales team faces the same question: *which clinics do we contact today, and why?* Today, that's mostly intuition. We turn five years of sales history into a daily ranked call list."

(Pause. Point at the **Commodities** card.)

> "The brief is explicit: commodities and technical products need different logic. **Commodities** — anaesthesia, biosecurity. Recurring purchases. We compare each clinic to its purchase potential, with a realistic capture impact, not a theoretical maximum."

(Point at the **Technical** card.)

> "**Technical products** — biomaterials. Sporadic, case-driven. We compare each clinic to its **own** historical pattern, with a year-over-year baseline so August holidays aren't read as churn."

(Point at the footer line.)

> "Output: ranked daily alerts with reason, urgency, channel, and full traceability."

(Move to slide 3 — or directly into the live demo.)

---

## Slide 3 — Numbers + Scorecard + Thanks

**🕒 Time:** 60 seconds.
**👀 Show:** Hold for a beat at each big number, then the scorecard, then close.

**🎤 Say:**
> "For the latest day in the dataset: **four thousand two hundred seventy-one alerts**, of which **one thousand three hundred** are high priority. Total expected commercial impact: **eleven point six million euros.**"

(Point at the scorecard grid.)

> "All eight brief deliverables — shipped. Purchase prediction, churn risk, capture windows, interpretable alerts, prioritisation, daily operation, CRM-ready architecture, and a learning loop. Plus all four prioritisation signals from the brief in the score formula: impact, urgency, client value, and conversion probability."

(Pause. Smile.)

> "Thank you — happy to take questions."

(Stop talking. Wait.)

---

## Backup answers (Q&A)

These are the predictable questions. **Memorise the first sentence of each.**

### "Did you measure predictive accuracy?"
> "Honestly, no. Measuring intervention effectiveness needs a control group — that's phase two. What we *can* defend is the **logic**: every alert is traceable, every threshold is documented, every multiplier in the score has a rationale."

### "Why these specific thresholds?"
> "They're heuristics, calibrated to the brief's segments. The Learning loop tab shows their conversion rates — when we have ≥500 real outcomes, the threshold-tuning module adjusts them automatically."

### "Won't this fire the same silent alert every day?"
> "No. When an outcome is recorded as won, lost, or false positive, that combination of client × family × type is **snoozed for thirty days**."

### "Is this Machine Learning?"
> "Deliberately not. The brief is explicit: *the key is analytical and commercial utility, not technical sophistication*. We use rule-based detection with a feedback loop. ML becomes a real option once we have ≥500 real labelled outcomes — until then, training would be self-deception."

### "What about the August drop?"
> "We measured the seasonal effect empirically — August is twenty-five to thirty-eight percent of the yearly average. Without seasonality awareness, the system would fire roughly fifteen hundred false-positive churn alerts every August. We use a year-over-year baseline plus a holiday flag — drop signals during August are suppressed unless year-over-year *also* shows a real decline."

### "How does this scale?"
> "The daily run takes about five seconds for six thousand clients. Linear in client count. The architecture is layered — adding a new country, family, or alert type doesn't touch the other layers."

### "Can a sales rep override an alert?"
> "Yes — every alert is auditable. The rep can drill into the trace features, see the raw numbers, and decide. If they dismiss it, the feedback loop captures the dismissal as a false positive with a reason — and that reason flows back to threshold tuning."

---

## Stage cheat sheet

| Situation | Action |
|---|---|
| Demo crashes mid-pitch | Skip the demo. Slide 3 tells the same story in numbers. |
| Going over time | Cut the second sentence of slide 2 (the "today is mostly intuition" line). |
| Going under time | Add: *"and we have an AI-narrated demo video on file too"* at the end of slide 3. |
| Network drops | Everything is local — no internet needed. |
| Unexpected question | Honest first sentence > pretending to know. Better to say "I'd need real outcome data to answer that" than overclaim. |

---

## Pre-flight checklist (do this 5 minutes before going on)

- [ ] `streamlit run src/dashboard.py` is running
- [ ] Browser open at `http://localhost:8501`
- [ ] Date picker set to **2025-12-29**
- [ ] **Client view** tab selected, with a high-score client pre-selected
- [ ] Slide deck open, on slide 1
- [ ] One glass of water nearby

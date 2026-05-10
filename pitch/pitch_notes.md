# Pitch notes — Inibsa Alert Marker (8-slide guided deck)

**File:** `pitch/Inibsa_Alert_Marker.pptx`
**Total target time:** 3-4 minutes for the slide portion (cover 10s + 6 sections × ~25s + close 30s).
**Live demo guide:** `pitch/demo_walkthrough_3min.md` (separate 3 min if you have the slot).

The deck follows the official guide's six sections (one slide each) plus a cover and a numbers/thanks slide.

| Slide | Section | Time |
|---|---|---|
| 1 | Cover (Mythos brand) | 10s |
| 2 | **Our approach** — central idea + why heuristics + advantage | 35s |
| 3 | **Analytical logic** — two-track + signals + noise → priority | 40s |
| 4 | **Data, variables, assumptions** — 3-column matrix | 35s |
| 5 | **Output** — alert anatomy + how it surfaces | 30s |
| 6 | **Technical info** — built / language / environment | 20s |
| 7 | **Day-to-day operation** — workflow + architecture | 30s |
| 8 | Numbers + 8/8 deliverables + Thanks | 25s |

---

## Slide 1 — Cover

**🎤 Say:**
> "We're Mythos Group. This is **Inibsa Alert Marker** — a daily commercial-alert engine for Inibsa's six thousand dental clinics."

---

## Slide 2 — Our approach

**🕒 35s · 👀 Point at the navy "central idea" bar, then the two cards.**

**🎤 Say:**
> "Our central idea: **turn five years of Inibsa's sales history into a daily ranked call list**. Every clinic that needs attention today, with a clear reason and a recommended action."

(Point at the left card.)

> "Why heuristics, not Machine Learning? The brief is explicit — *"the key is analytical and commercial utility, not technical sophistication"*. ML needs labelled outcomes we don't have yet. Rules can be tuned later by the feedback loop."

(Point at the right card.)

> "Our advantage: **explainable, defensible, fast.** Every alert traces back to its raw inputs. Every threshold is anchored to either an observation in the data or a brief requirement. Five seconds for six thousand clients."

---

## Slide 3 — Analytical logic

**🕒 40s · 👀 Top row first (two-track), then bottom row (noise, priority).**

**🎤 Say:**
> "Two parallel logics, because the brief insists on it and the data confirms it."

(Point at the left card.)

> "**Commodities** — anaesthesia, biosecurity. Recurring purchases, so we use a share-of-potential rule. Loyal, promiscuous, marginal, lost — each segment with a defined threshold."

(Point at the right card.)

> "**Technical products** — biomaterials. Sporadic. We compare each clinic to its OWN past pattern, with a year-over-year baseline so August holidays aren't read as churn."

(Point at the bottom-left card.)

> "Noise filtering: holiday flag suppresses August drops, post-campaign grace silences clients who just stocked up, snooze for thirty days after a sales rep records an outcome, cyclic-client filter on lost alerts."

(Point at the bottom-right card.)

> "**Priority** is one number: `score = impact × urgency × conversion_probability`. All four prioritisation signals from the brief in one formula."

---

## Slide 4 — Data, variables, assumptions

**🕒 35s · 👀 Three columns left to right.**

**🎤 Say:**
> "Five datasets, all cleaned. Direct variables from the source — date, units, value, IDs, potencial."

(Point at the navy middle column.)

> "Derived variables that we compute: share of potential at trailing twelve months, mean inter-purchase days, cycle progress, year-over-year baselines, conversion probability. The system **derives** the cyclicity from the data — we don't trust labels we don't have."

(Point at the right column.)

> "Key assumptions: cyclicity is inferred from purchase intervals; potencial is Inibsa's annual estimate. Returns and zero-cost units are flagged, not dropped."

(Point at the bottom of the right column.)

> "Crucially, **we cannot observe competitor purchases**. We INFER un-captured demand from the gap between observed sales and the potential estimate. A client buying only 27 percent of their potential, but still active, is promiscuous — they're buying somewhere else."

---

## Slide 5 — Output

**🕒 30s · 👀 Big code-block on the left, then 3 surface cards on the right.**

**🎤 Say:**
> "One alert looks like this. Twelve fields, machine-readable, every metric documented."

(Point at the `motivo` and `trace_features` lines.)

> "The motive is human-readable. The trace_features are the raw numbers — every threshold that fired this alert. **No black box.** A sales rep clicks one alert and sees exactly why."

(Point at the right side.)

> "How is it surfaced? Three ways. The interactive **Streamlit dashboard** with three tabs. CSV or **HubSpot Tasks JSON** export. And in the dashboard's Client view, the four sales-team-readable categories: Lost, Loss risk, Sales opportunity, Healthy."

---

## Slide 6 — Technical info

**🕒 20s · 👀 Three columns.**

**🎤 Say:**
> "How we built it: AI-assisted with Claude Code, but every change went through manual review. Thirteen pull requests. Twenty-one passing smoke tests."

(Point at the middle column.)

> "Language: **Python 3.10 plus**, with pandas, streamlit, and a couple of helpers. No exotic dependencies."

(Point at the right column — navy.)

> "Environment: **macOS, Linux, or Windows**. Single command — `streamlit run src/dashboard.py`. No internet required at runtime. Five seconds for the daily compute. Self-contained in the repo."

---

## Slide 7 — Day-to-day operation

**🕒 30s · 👀 Workflow on the left, architecture on the right.**

**🎤 Say:**
> "Day-to-day. Eight in the morning, the engine runs. Eight-oh-five, the sales team opens the dashboard. Eight-ten, a rep clicks a client and sees the cycle status, the reason, and the action. Throughout the day, they call or visit. End of day, they record the outcome."

(Point at the architecture stack on the right.)

> "Minimum architecture: **four layers**. Data, analytical, activation, feedback. Each independent. Standalone today, CRM-ready tomorrow."

(Point at the demo callout.)

> "We have a 3-minute live demo guide and a 2-minute AI-narrated demo video on file."

---

## Slide 8 — Numbers + Thanks

**🕒 25s · 👀 Hold for a beat at each big number.**

**🎤 Say:**
> "For the latest day in the dataset: **4,271 alerts**, of which **1,300 are high priority**. Total expected commercial impact: **€11.6 million.**"

(Point at the scorecard grid.)

> "All eight brief deliverables — shipped. Plus all four prioritisation signals from the brief in the score formula."

(Pause.)

> "Thank you. Happy to take questions."

(Stop talking.)

---

## Backup answers (Q&A)

### "Did you measure predictive accuracy?"
> "Honestly, no. Measuring intervention effectiveness needs a control group — that's phase two. What we *can* defend is the logic: every alert is traceable, every threshold is documented."

### "Why these specific thresholds?"
> "Heuristics calibrated to the brief's segments. The Learning loop tab shows their conversion rates — when we have ≥500 real outcomes, the threshold-tuning module adjusts them automatically."

### "Won't this fire the same silent alert every day?"
> "No. After a sales rep records won, lost, or false positive, that combination of client × family × type is **snoozed for thirty days**."

### "Is this Machine Learning?"
> "Deliberately not. The brief is explicit: *the key is analytical and commercial utility*. We use rules with a feedback loop. ML becomes a real option once we have ≥500 labelled outcomes."

### "What about the August drop?"
> "We measured it empirically — August is twenty-five to thirty-eight percent of yearly average. Our YoY baseline plus holiday flag suppresses August drops unless YoY also confirms a real decline."

### "How does this scale?"
> "Five seconds for six thousand clients. Linear in client count. Adding a new country, family, or alert type doesn't touch the other layers."

### "Can a sales rep override an alert?"
> "Yes. Every alert is auditable — drill in, see the raw numbers, decide. Dismissals are captured as false positives with a reason — and that reason flows back to threshold tuning."

---

## Stage cheat sheet

| Situation | Action |
|---|---|
| Demo crashes mid-pitch | Skip the demo; slide 8 tells the story numerically. |
| Going over time | Cut slide 6 (Technical info) — most expendable. |
| Going under time | Add detail on slide 4 — the un-captured-consumption inference is rich. |
| Network drops | Everything is local — no internet needed. |
| Unexpected question | Honest first sentence > pretending to know. |

---

## Pre-flight checklist (5 minutes before going on)

- [ ] `streamlit run src/dashboard.py` is running
- [ ] Browser open at `http://localhost:8501`
- [ ] Date picker set to **2025-12-29**
- [ ] **Client view** tab selected, with a high-score client pre-selected
- [ ] Slide deck open, on slide 1
- [ ] One glass of water nearby

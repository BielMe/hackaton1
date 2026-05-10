"""
Unified Inibsa Alert Marker pitch deck — 4 slides.

Combines the short pitch with a compact heuristic-design slide:
  1. Cover            — Mythos brand (uses pitch/cover.png if present)
  2. Opportunity      — problem + two-track approach
  3. Heuristic Design — 8 cases in a compact grid
  4. Numbers          — proof + 8/8 deliverables + thanks

Live numbers pulled at build time from generate_alerts().
"""
from __future__ import annotations
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ---- Mythos brand palette ----
NAVY   = RGBColor(0x1B, 0x2A, 0x4A)
STEEL  = RGBColor(0x5A, 0x7A, 0x9A)
LIGHT  = RGBColor(0xC9, 0xD4, 0xE3)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
INK    = RGBColor(0x1A, 0x1A, 0x1A)
GREY   = RGBColor(0x6B, 0x6B, 0x6B)
SOFT   = RGBColor(0xF4, 0xF6, 0xFA)
ACCENT = RGBColor(0x2E, 0x6F, 0xA8)

H_FONT = "Calibri"
B_FONT = "Calibri"


def fill(shape, rgb):
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    shape.line.fill.background()


def add_text(slide, x, y, w, h, text, *, size=18, bold=False, colour=INK,
             font=B_FONT, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0)
    tf.margin_top = tf.margin_bottom = Inches(0)
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = colour
    return box


def add_bullets(slide, x, y, w, h, items, *, size=14, colour=INK, dot=ACCENT):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(6)
        r1 = p.add_run(); r1.text = "•  "; r1.font.size = Pt(size + 2)
        r1.font.bold = True; r1.font.color.rgb = dot; r1.font.name = B_FONT
        r2 = p.add_run(); r2.text = item; r2.font.size = Pt(size)
        r2.font.color.rgb = colour; r2.font.name = B_FONT
    return box


def fmt_eur(n):
    if n >= 1e6: return f"€{n/1e6:.1f}M"
    if n >= 1e3: return f"€{n/1e3:.0f}K"
    return f"€{n:,.0f}"


# ---- Live numbers ----
def _numbers():
    from smart_demand_signals import generate_alerts
    a = generate_alerts("2025-12-29")
    return {
        "n_alerts":     len(a),
        "n_high":       int((a["prioridad"] == "High").sum()),
        "total_impact": float(a["expected_impact_eur"].sum()),
    }


NUMS = _numbers()


# ---- Build deck ----
prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


# ====================================================================
# SLIDE 1 — COVER (Mythos brand)
# ====================================================================
s = prs.slides.add_slide(blank)

cover_path = ROOT / "pitch" / "cover.png"
if cover_path.exists():
    s.shapes.add_picture(str(cover_path), 0, 0, width=Inches(13.333), height=Inches(7.5))
else:
    # Recreate the cover layout programmatically
    logo_x = Inches(2.0)
    logo_y = Inches(2.0)
    logo_size = Inches(2.6)

    left_v = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, logo_x, logo_y,
                                Inches(0.40), logo_size); fill(left_v, NAVY)
    right_v = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                  logo_x + logo_size - Inches(0.40), logo_y,
                                  Inches(0.40), logo_size); fill(right_v, NAVY)
    top_l = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                logo_x, logo_y, Inches(0.95), Inches(0.40))
    fill(top_l, NAVY)
    top_r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                logo_x + logo_size - Inches(0.95), logo_y,
                                Inches(0.95), Inches(0.40))
    fill(top_r, NAVY)

    bars_x_start = logo_x + Inches(0.55)
    bars_y_base = logo_y + logo_size - Inches(0.20)
    bar_w = Inches(0.30); gap = Inches(0.05)
    heights = [0.45, 0.75, 1.05, 1.35]
    colours = [LIGHT, STEEL, STEEL, NAVY]
    for i, h in enumerate(heights):
        bar = s.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            bars_x_start + i * (bar_w + gap),
            bars_y_base - Inches(h),
            bar_w, Inches(h))
        fill(bar, colours[i])

    add_text(s, Inches(1.4), logo_y + logo_size + Inches(0.40),
             Inches(3.8), Inches(0.6),
             "MYTHOS", size=32, bold=False, colour=NAVY,
             font=H_FONT, align=PP_ALIGN.CENTER)
    underline = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                    Inches(2.6), logo_y + logo_size + Inches(1.05),
                                    Inches(1.4), Inches(0.04))
    fill(underline, NAVY)

    div = s.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                              Inches(6.2), Inches(1.7),
                              Inches(0.02), Inches(4.0))
    fill(div, GREY)

    add_text(s, Inches(6.7), Inches(2.6), Inches(6.4), Inches(1.0),
             "Inibsa Alert", size=54, bold=True, colour=INK,
             font=H_FONT, align=PP_ALIGN.LEFT)
    add_text(s, Inches(6.7), Inches(3.4), Inches(6.4), Inches(1.0),
             "Marker", size=54, bold=True, colour=INK,
             font=H_FONT, align=PP_ALIGN.LEFT)
    add_text(s, Inches(6.7), Inches(4.5), Inches(6.4), Inches(0.5),
             "Mythos Group", size=20, colour=GREY, font=B_FONT)
    add_text(s, Inches(6.7), Inches(4.95), Inches(6.4), Inches(0.5),
             "InterHack 2026", size=20, colour=GREY, font=B_FONT)


# ====================================================================
# SLIDE 2 — Opportunity + Approach
# ====================================================================
s = prs.slides.add_slide(blank)

add_text(s, Inches(0.7), Inches(0.45), Inches(12), Inches(0.7),
         "Every morning, a 6,000-clinic question",
         size=30, bold=True, colour=NAVY, font=H_FONT)
add_text(s, Inches(0.7), Inches(1.10), Inches(12), Inches(0.5),
         "Which clinics do we contact today, and why? "
         "We turn 5 years of sales history into a daily ranked call list.",
         size=15, colour=GREY, font=B_FONT)

left = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                          Inches(0.7), Inches(2.0), Inches(6.0), Inches(4.7))
fill(left, SOFT); left.line.fill.background()
add_text(s, Inches(1.0), Inches(2.2), Inches(5.5), Inches(0.4),
         "COMMODITIES", size=11, bold=True, colour=ACCENT, font=H_FONT)
add_text(s, Inches(1.0), Inches(2.55), Inches(5.5), Inches(0.6),
         "Anaesthesia · Biosecurity",
         size=22, bold=True, colour=NAVY, font=H_FONT)
add_text(s, Inches(1.0), Inches(3.20), Inches(5.5), Inches(0.4),
         "Recurring purchases. Predictable consumption.",
         size=13, colour=INK, font=B_FONT)
add_bullets(s, Inches(1.0), Inches(3.7), Inches(5.5), Inches(2.7), [
    "Compare each clinic to its purchase potential",
    "Loyal · Promiscuous · Marginal · Lost",
    "Realistic capture impact (30-50% growth)",
], size=13)

right = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                           Inches(6.85), Inches(2.0), Inches(6.0), Inches(4.7))
fill(right, NAVY); right.line.fill.background()
add_text(s, Inches(7.15), Inches(2.2), Inches(5.5), Inches(0.4),
         "TECHNICAL PRODUCTS", size=11, bold=True, colour=LIGHT, font=H_FONT)
add_text(s, Inches(7.15), Inches(2.55), Inches(5.5), Inches(0.6),
         "Biomaterials",
         size=22, bold=True, colour=WHITE, font=H_FONT)
add_text(s, Inches(7.15), Inches(3.20), Inches(5.5), Inches(0.4),
         "Sporadic purchases. Case-driven demand.",
         size=13, colour=WHITE, font=B_FONT)
add_bullets(s, Inches(7.15), Inches(3.7), Inches(5.5), Inches(2.7), [
    "Compare each clinic to its OWN history",
    "Year-over-year baseline (neutralises August)",
    "Frequency drop · Volume drop · Absence · Anomaly",
], size=13, colour=WHITE, dot=LIGHT)

add_text(s, Inches(0.7), Inches(6.85), Inches(12), Inches(0.4),
         "Output: ranked daily alerts with reason, urgency, channel, and full traceability.",
         size=13, bold=True, colour=NAVY, font=B_FONT, align=PP_ALIGN.CENTER)


# ====================================================================
# SLIDE 3 — Heuristic Design (compact, 8 cases in a 4×2 grid)
# ====================================================================
s = prs.slides.add_slide(blank)

add_text(s, Inches(0.7), Inches(0.45), Inches(12), Inches(0.7),
         "Heuristic design — 8 cases, no black box",
         size=30, bold=True, colour=NAVY, font=H_FONT)
add_text(s, Inches(0.7), Inches(1.10), Inches(12), Inches(0.5),
         "Every rule is anchored to either an observation in the data or a requirement in the brief.",
         size=14, colour=GREY, font=B_FONT)

# 4×2 grid of cases
cases = [
    ("01  Two-track logic",
     "Commodities (predictable) and technical (sporadic) get separate rules.",
     "Brief requirement"),
    ("02  August / seasonality",
     "Year-over-year baseline + holiday flag — neutralises August (0.25× yearly avg).",
     "Empirical"),
    ("03  Lost-client filter",
     "Only fire `lost` for cyclic clients (≥3 buys, ≥€200, cycle ≤365d).",
     "Signal-to-noise"),
    ("04  Post-campaign grace",
     "Heavy buyers in promo windows are silenced until expected restock date.",
     "Brief caveat"),
    ("05  Outcome-driven snooze",
     "After won/lost/false_positive, that (cliente×fam×tipo) is muted 30 days.",
     "Brief operational"),
    ("06  Dynamic contact window",
     "Window adapts to each client's avg cycle — overdue tightens, on-cycle exact.",
     "Per-client rhythm"),
    ("07  Realistic capture impact",
     "Promiscuous impact = current × 0.3–0.5 — defensible, not theoretical.",
     "Defensibility"),
    ("08  Conversion probability",
     "score = impact × urgency × conv_prob (4th brief signal).",
     "Brief"),
]

cols = 4
rows = 2
grid_x = Inches(0.7)
grid_y = Inches(1.95)
total_w = Inches(11.93)
total_h = Inches(4.4)
gap_x = Inches(0.18)
gap_y = Inches(0.2)
cw = Emu(int((total_w.emu - (cols - 1) * gap_x.emu) / cols))
ch = Emu(int((total_h.emu - (rows - 1) * gap_y.emu) / rows))

for i, (title, body, anchor) in enumerate(cases):
    c = i % cols
    r = i // cols
    x = grid_x + c * (cw + gap_x)
    y = grid_y + r * (ch + gap_y)
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, ch)
    fill(card, SOFT); card.line.fill.background()
    # Header
    add_text(s, x + Inches(0.18), y + Inches(0.14),
             cw - Inches(0.36), Inches(0.4),
             title, size=12, bold=True, colour=NAVY, font=H_FONT)
    # Body
    add_text(s, x + Inches(0.18), y + Inches(0.55),
             cw - Inches(0.36), ch - Inches(1.1),
             body, size=10, colour=INK, font=B_FONT)
    # Anchor pill
    add_text(s, x + Inches(0.18), y + ch - Inches(0.4),
             cw - Inches(0.36), Inches(0.3),
             "→  " + anchor, size=9, bold=True, colour=ACCENT, font=H_FONT)

# Footer
add_text(s, Inches(0.7), Inches(6.55), Inches(12), Inches(0.4),
         "All four prioritisation signals from the brief are in the score: "
         "impact × urgency × client value × conversion probability.",
         size=13, bold=True, colour=NAVY, font=B_FONT, align=PP_ALIGN.CENTER)
add_text(s, Inches(0.7), Inches(6.95), Inches(12), Inches(0.35),
         "No black box. Every threshold and multiplier is documented in the code.",
         size=12, colour=GREY, font=B_FONT, align=PP_ALIGN.CENTER)


# ====================================================================
# SLIDE 4 — Numbers + Scorecard + Thanks
# ====================================================================
s = prs.slides.add_slide(blank)

add_text(s, Inches(0.7), Inches(0.45), Inches(12), Inches(0.7),
         "By the numbers · 8 of 8 deliverables shipped",
         size=30, bold=True, colour=NAVY, font=H_FONT)

metrics = [
    (f"{NUMS['n_alerts']:,}", "alerts generated today"),
    (f"{NUMS['n_high']:,}",   "High priority"),
    (fmt_eur(NUMS['total_impact']), "expected commercial impact"),
]
y_metrics = Inches(1.6)
for i, (val, lbl) in enumerate(metrics):
    x = Inches(0.7 + i * 4.2)
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              x, y_metrics, Inches(4.0), Inches(1.7))
    fill(card, SOFT); card.line.fill.background()
    add_text(s, x, y_metrics + Inches(0.25), Inches(4.0), Inches(0.9),
             val, size=44, bold=True, colour=NAVY, font=H_FONT,
             align=PP_ALIGN.CENTER)
    add_text(s, x, y_metrics + Inches(1.20), Inches(4.0), Inches(0.4),
             lbl, size=13, colour=GREY, font=B_FONT, align=PP_ALIGN.CENTER)

deliverables = [
    "Purchase prediction (commodities)",
    "Early churn-risk (technical)",
    "Capture-window identification",
    "Interpretable, actionable alerts",
    "Operational prioritisation",
    "Daily-operation proposal",
    "Standalone-to-CRM evolution path",
    "Learning capability (feedback loop)",
]
y_sc = Inches(3.6)
cols = 2
cw = Inches(6.0)
ch = Inches(0.55)
for i, txt in enumerate(deliverables):
    c = i % cols
    r = i // cols
    x = Inches(0.7 + c * 6.15)
    y = y_sc + r * Inches(0.65)
    tick = s.shapes.add_shape(MSO_SHAPE.OVAL, x, y, Inches(0.32), Inches(0.32))
    fill(tick, ACCENT)
    add_text(s, x, y, Inches(0.32), Inches(0.32),
             "✓", size=14, bold=True, colour=WHITE, font=H_FONT,
             align=PP_ALIGN.CENTER)
    add_text(s, x + Inches(0.50), y + Inches(0.04),
             cw - Inches(0.5), Inches(0.4),
             txt, size=13, colour=INK, font=B_FONT)

ty = Inches(6.6)
add_text(s, Inches(0), ty, Inches(13.333), Inches(0.5),
         "Thank you · Questions?",
         size=18, bold=True, colour=NAVY, font=H_FONT, align=PP_ALIGN.CENTER)
add_text(s, Inches(0), ty + Inches(0.45), Inches(13.333), Inches(0.4),
         "Mythos Group · github.com/SH-SW/InterHack2026",
         size=11, colour=GREY, font=B_FONT, align=PP_ALIGN.CENTER)


# ---- Save ----
out = ROOT / "pitch" / "Inibsa_Alert_Marker.pptx"
prs.save(out)
print(f"✅ Wrote {out}  ({out.stat().st_size//1024} KB)  ·  {len(prs.slides)} slides")
print(f"   Live numbers: {NUMS['n_alerts']:,} alerts · {NUMS['n_high']:,} High · {fmt_eur(NUMS['total_impact'])}")
print(f"   Cover image: {'pitch/cover.png (used)' if cover_path.exists() else 'recreated programmatically'}")

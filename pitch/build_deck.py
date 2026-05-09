"""
Build the Smart Demand Signals pitch deck.

Design:
  - Primary  : Deep teal  #0F4C5C (~60% of visual weight, used in dark slides)
  - Accent   : Coral      #E36C3D (sparingly, for emphasis/dots/highlights)
  - Light    : White       #FFFFFF
  - Text     : Near-black #1A1A1A on light, #FFFFFF on dark
  - Motif    : Small coral filled circle next to section headers
  - Structure: dark cover → white content → dark numbers → white content → dark thanks
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

# ---------- Colours ----------
TEAL    = RGBColor(0x0F, 0x4C, 0x5C)
TEAL_70 = RGBColor(0x35, 0x70, 0x80)   # subtle variation
CORAL   = RGBColor(0xE3, 0x6C, 0x3D)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
INK     = RGBColor(0x1A, 0x1A, 0x1A)
GREY    = RGBColor(0x6B, 0x6B, 0x6B)
LIGHT   = RGBColor(0xF2, 0xEC, 0xE4)   # warm light card

H_FONT = "Calibri"
B_FONT = "Calibri"

# ---------- Live numbers ----------
def _numbers():
    from smart_demand_signals import generate_alerts
    a = generate_alerts("2025-12-29")
    return {
        "n_alerts":       len(a),
        "n_high":         int((a["prioridad"] == "High").sum()),
        "total_impact":   float(a["expected_impact_eur"].sum()),
        "tipo_silent":    int((a["tipo_alerta"] == "silent").sum()),
        "tipo_capture":   int((a["tipo_alerta"] == "capture_window").sum()),
        "tipo_lost":      int((a["tipo_alerta"] == "lost").sum()),
        "tipo_churn":     int((a["tipo_alerta"] == "churn_risk").sum()),
        "tipo_spike":     int((a["tipo_alerta"] == "opportunity_spike").sum()),
        "top_alert_eur":  float(a["expected_impact_eur"].iloc[0]),
        "top_alert_prov": str(a["provincia"].iloc[0]),
    }

NUMS = _numbers()

# ---------- Helpers ----------
def fill(shape, rgb: RGBColor):
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    shape.line.fill.background()

def line_no(shape):
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

def add_bullets(slide, x, y, w, h, items, *, size=16, colour=INK, dot=CORAL):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(8)
        r1 = p.add_run(); r1.text = "•  "; r1.font.size = Pt(size + 2)
        r1.font.bold = True; r1.font.color.rgb = dot; r1.font.name = B_FONT
        r2 = p.add_run(); r2.text = item; r2.font.size = Pt(size)
        r2.font.color.rgb = colour; r2.font.name = B_FONT
    return box

def add_circle(slide, x, y, d, rgb=CORAL):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, d, d)
    fill(s, rgb)
    return s

def add_motif_dot(slide, x, y):
    add_circle(slide, x, y, Inches(0.18))

def slide_title(slide, text, *, dark=False, x=Inches(0.6), y=Inches(0.45)):
    """Slide title with motif dot."""
    add_motif_dot(slide, x, y + Inches(0.18))
    add_text(slide, x + Inches(0.35), y, Inches(11), Inches(0.7),
             text, size=32, bold=True,
             colour=WHITE if dark else INK, font=H_FONT)

def add_dark_bg(slide):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0,
                                Inches(13.333), Inches(7.5))
    fill(bg, TEAL); line_no(bg)
    return bg

def fmt_eur(n):
    if n >= 1e6:
        return f"€{n/1e6:.1f}M"
    if n >= 1e3:
        return f"€{n/1e3:.0f}K"
    return f"€{n:,.0f}"

# ---------- Build deck ----------
prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]

# ====================================================================
# Slide 1 — Cover (dark)
# ====================================================================
s = prs.slides.add_slide(blank)
add_dark_bg(s)
# Decorative coral disk in upper right
add_circle(s, Inches(11.2), Inches(0.5), Inches(1.5))
# Inset white ring
ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(11.45), Inches(0.75), Inches(1.0), Inches(1.0))
fill(ring, TEAL); ring.line.color.rgb = WHITE; ring.line.width = Pt(2.5)
# Title block
add_text(s, Inches(0.8), Inches(2.4), Inches(11), Inches(1.4),
         "Smart Demand", size=72, bold=True, colour=WHITE, font=H_FONT)
add_text(s, Inches(0.8), Inches(3.4), Inches(11), Inches(1.4),
         "Signals", size=72, bold=True, colour=CORAL, font=H_FONT)
# Subtitle
add_text(s, Inches(0.8), Inches(4.7), Inches(11), Inches(0.6),
         "Daily commercial alerts for 6,000 dental clinics",
         size=22, colour=WHITE, font=B_FONT)
# Footer
add_text(s, Inches(0.8), Inches(6.7), Inches(8), Inches(0.4),
         "Inibsa  ·  Interhack BCN 2026",
         size=14, colour=RGBColor(0xCA, 0xDC, 0xFC), font=B_FONT)

# ====================================================================
# Slide 2 — The problem
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "Every morning, a 6,000-clinic question")
# Big quote — single line each, generous width
add_text(s, Inches(0.8), Inches(1.85), Inches(12.0), Inches(0.9),
         "“Which of our clinics should we contact today,",
         size=32, bold=True, colour=INK, font=H_FONT)
add_text(s, Inches(0.8), Inches(2.75), Inches(12.0), Inches(0.9),
         "and why?”", size=32, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(0.8), Inches(3.95), Inches(11), Inches(0.5),
         "Today, this is mostly intuition + scattered KPIs.",
         size=18, colour=GREY, font=B_FONT)

# Three stat cards bottom
for i, (val, lbl) in enumerate([("6,000", "dental clinics"),
                                ("5 years", "of sales history"),
                                ("25 SKUs", "across 4 sub-families")]):
    x = Inches(0.8 + i * 4.0)
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              x, Inches(5.0), Inches(3.7), Inches(1.7))
    fill(card, LIGHT); line_no(card)
    add_text(s, x + Inches(0.3), Inches(5.2), Inches(3.4), Inches(0.8),
             val, size=36, bold=True, colour=TEAL, font=H_FONT)
    add_text(s, x + Inches(0.3), Inches(6.0), Inches(3.4), Inches(0.5),
             lbl, size=14, colour=GREY, font=B_FONT)

# ====================================================================
# Slide 3 — Two products, two brains
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "Two products. Two brains.")
add_text(s, Inches(0.95), Inches(1.15), Inches(11), Inches(0.5),
         "The brief insists on it — and the data confirms it.",
         size=15, colour=GREY, font=B_FONT)

# Left card — Commodities
left = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                          Inches(0.8), Inches(1.85), Inches(5.9), Inches(5.1))
fill(left, LIGHT); line_no(left)
add_text(s, Inches(1.1), Inches(2.05), Inches(5.5), Inches(0.5),
         "COMMODITIES", size=12, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(1.1), Inches(2.45), Inches(5.5), Inches(0.7),
         "Anestesia · Bioseguridad",
         size=24, bold=True, colour=TEAL, font=H_FONT)
add_text(s, Inches(1.1), Inches(3.2), Inches(5.5), Inches(0.5),
         "Recurring purchases, predictable consumption.",
         size=14, colour=INK, font=B_FONT)
add_bullets(s, Inches(1.1), Inches(3.85), Inches(5.5), Inches(3.0), [
    "Compare against the clinic's purchase potential",
    "Loyal: capturing ≥30% of potential",
    "Promiscuous: split with competitors",
    "Marginal: residual buyers",
    "Churn-risk: was active, now silent or dropping",
], size=14)

# Right card — Technical
right = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                           Inches(6.95), Inches(1.85), Inches(5.9), Inches(5.1))
fill(right, TEAL); line_no(right)
add_text(s, Inches(7.25), Inches(2.05), Inches(5.5), Inches(0.5),
         "PRODUCTOS TÉCNICOS", size=12, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(7.25), Inches(2.45), Inches(5.5), Inches(0.7),
         "Biomateriales",
         size=24, bold=True, colour=WHITE, font=H_FONT)
add_text(s, Inches(7.25), Inches(3.2), Inches(5.5), Inches(0.5),
         "Sporadic purchases, case-driven demand.",
         size=14, colour=WHITE, font=B_FONT)
add_bullets(s, Inches(7.25), Inches(3.85), Inches(5.5), Inches(3.0), [
    "Compare each clinic to its own historical pattern",
    "Year-over-year baseline (neutralises seasonality)",
    "Detect drops in frequency, volume, or absence",
    "Distinguish normal pause vs. real deterioration",
    "Holiday-aware (August, Christmas)",
], size=14, colour=WHITE, dot=CORAL)

# ====================================================================
# Slide 4 — Pipeline
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "From data to commercial action")

stages = [
    ("Purchase\nhistory",       "5 years × daily granularity"),
    ("Signal\ndetection",       "Two parallel logics"),
    ("Daily\nalert",            "Score, reason, channel, traceability"),
    ("Commercial\naction",      "Delegado · Televenta · Marketing"),
]
y = Inches(2.6)
total_w = Inches(12.0)
gap = Inches(0.25)
n = len(stages)
arrow_w = Inches(0.4)
box_w = Emu(int((total_w.emu - (n - 1) * (gap.emu + arrow_w.emu)) / n))
x = Inches(0.65)
for i, (title, sub) in enumerate(stages):
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y,
                             box_w, Inches(2.0))
    is_last = i == n - 1
    fill(box, TEAL if is_last else LIGHT); line_no(box)
    title_clr = WHITE if is_last else TEAL
    sub_clr   = RGBColor(0xCA, 0xDC, 0xFC) if is_last else GREY
    add_text(s, x, y + Inches(0.45), box_w, Inches(1.0),
             title, size=20, bold=True, colour=title_clr, font=H_FONT,
             align=PP_ALIGN.CENTER)
    add_text(s, x + Inches(0.2), y + Inches(1.45), box_w - Inches(0.4),
             Inches(0.5), sub, size=11, colour=sub_clr, font=B_FONT,
             align=PP_ALIGN.CENTER)
    if i < n - 1:
        ax = x + box_w + Inches(0.05)
        ay = y + Inches(0.85)
        arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, ax, ay,
                                   arrow_w, Inches(0.3))
        fill(arrow, CORAL); line_no(arrow)
    x = x + box_w + gap + arrow_w

add_text(s, Inches(0.65), Inches(5.4), Inches(12), Inches(0.5),
         "One function. One date input. End-to-end output.",
         size=15, colour=GREY, font=B_FONT, align=PP_ALIGN.CENTER)

# ====================================================================
# Slide 5 — Alert anatomy
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "What's in an alert")

# Code-like block on the left
code_lines = [
    ("alert_id",           '"ALT-20251229-000001"'),
    ("id_cliente",         f'"{NUMS["top_alert_prov"][:0]}40439"'),
    ("provincia",          '"Zaragoza"'),
    ("familia",            '"Categoria C2"  (Bioseguridad)'),
    ("tipo_alerta",        '"capture_window"'),
    ("prioridad",          '"High"'),
    ("score",              '57,875'),
    ("expected_impact_eur",'82,679'),
    ("canal",              '"delegado"'),
    ("contact_window_days", "7"),
    ("motivo",             '"Cliente promiscuo: 6% del potencial..."'),
    ("trace_features",      '{ share: 0.06, potencial: 87,672, ... }'),
]
panel = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                           Inches(0.8), Inches(1.6), Inches(7.0), Inches(5.4))
fill(panel, INK); line_no(panel)
yy = Inches(1.85)
for k, v in code_lines:
    add_text(s, Inches(1.05), yy, Inches(2.4), Inches(0.36),
             k, size=12, bold=True, colour=CORAL, font="Consolas")
    add_text(s, Inches(3.45), yy, Inches(4.3), Inches(0.36),
             v, size=12, colour=WHITE, font="Consolas")
    yy = yy + Inches(0.40)

# Annotations on the right
add_text(s, Inches(8.2), Inches(1.85), Inches(4.8), Inches(0.5),
         "Decision unit", size=12, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(8.2), Inches(2.2), Inches(4.8), Inches(0.6),
         "client × familia × motivo × momento", size=15, colour=INK, font=B_FONT)

add_text(s, Inches(8.2), Inches(3.0), Inches(4.8), Inches(0.5),
         "Prioritisation", size=12, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(8.2), Inches(3.35), Inches(4.8), Inches(0.6),
         "score = impact × urgency", size=15, colour=INK, font=B_FONT)

add_text(s, Inches(8.2), Inches(4.15), Inches(4.8), Inches(0.5),
         "Channel routing", size=12, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(8.2), Inches(4.5), Inches(4.8), Inches(0.6),
         "delegado / televenta / marketing", size=15, colour=INK, font=B_FONT)

add_text(s, Inches(8.2), Inches(5.3), Inches(4.8), Inches(0.5),
         "Traceability", size=12, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(8.2), Inches(5.65), Inches(4.8), Inches(1.4),
         "Every metric that fired the alert is in the trace. "
         "Drill into any alert and see the raw numbers. No black box.",
         size=13, colour=INK, font=B_FONT)

# ====================================================================
# Slide 6 — By the numbers (dark)
# ====================================================================
s = prs.slides.add_slide(blank)
add_dark_bg(s)
add_circle(s, Inches(0.6), Inches(0.6), Inches(0.18))
add_text(s, Inches(0.95), Inches(0.45), Inches(11), Inches(0.7),
         "By the numbers", size=32, bold=True, colour=WHITE, font=H_FONT)
add_text(s, Inches(0.95), Inches(1.15), Inches(11), Inches(0.5),
         "Generated for 2025-12-29", size=16, colour=RGBColor(0xCA,0xDC,0xFC), font=B_FONT)

# Three big stats
stats = [
    (f"{NUMS['n_alerts']:,}",       "alerts generated today"),
    (f"{NUMS['n_high']:,}",          "High priority"),
    (fmt_eur(NUMS['total_impact']), "expected commercial impact"),
]
xs = [Inches(0.8), Inches(5.0), Inches(9.2)]
for (val, lbl), x in zip(stats, xs):
    add_text(s, x, Inches(2.6), Inches(4.0), Inches(1.6),
             val, size=72, bold=True, colour=CORAL, font=H_FONT,
             align=PP_ALIGN.LEFT)
    add_text(s, x, Inches(4.4), Inches(4.0), Inches(0.6),
             lbl, size=16, colour=WHITE, font=B_FONT)

# Distribution callout
add_text(s, Inches(0.8), Inches(5.6), Inches(11), Inches(0.5),
         "By alert type", size=13, bold=True, colour=CORAL, font=H_FONT)
parts = [
    ("silent",            NUMS["tipo_silent"]),
    ("capture_window",    NUMS["tipo_capture"]),
    ("lost",              NUMS["tipo_lost"]),
    ("churn_risk",        NUMS["tipo_churn"]),
    ("opportunity_spike", NUMS["tipo_spike"]),
]
strip = "   ·   ".join(f"{lbl} {n:,}" for lbl, n in parts)
add_text(s, Inches(0.8), Inches(6.0), Inches(11.7), Inches(0.5),
         strip, size=16, colour=WHITE, font=B_FONT)

# ====================================================================
# Slide 7 — Live demo
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "Live demo · 3 minutes")

steps = [
    ("01", "Daily cadence",
     "Drag the date picker back to 2024-06-30. The alert table changes. "
     "Same code, any historical date — the system is idempotent."),
    ("02", "Drill into one alert",
     "Pick the top alert. Read the motivo. Click Trace features. "
     "See the raw numbers that fired it. No black box."),
    ("03", "Learning loop",
     "Switch to the Learning loop tab. 120 mocked outcomes show the system "
     "self-tuning: capture_window converts at 33%, silent at 11%."),
]
y = Inches(1.6)
for code, title, desc in steps:
    # Number badge
    badge = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), y,
                               Inches(0.85), Inches(0.85))
    fill(badge, CORAL); line_no(badge)
    add_text(s, Inches(0.8), y + Inches(0.16), Inches(0.85), Inches(0.6),
             code, size=18, bold=True, colour=WHITE, font=H_FONT,
             align=PP_ALIGN.CENTER)
    add_text(s, Inches(2.0), y, Inches(10.5), Inches(0.5),
             title, size=22, bold=True, colour=TEAL, font=H_FONT)
    add_text(s, Inches(2.0), y + Inches(0.55), Inches(10.5), Inches(1.0),
             desc, size=14, colour=INK, font=B_FONT)
    y = y + Inches(1.7)

# ====================================================================
# Slide 8 — Architecture
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "Layered. CRM-agnostic. Daily idempotent.")

layers = [
    ("Feedback layer",     "alert_outcomes.csv → metrics → rule tuning",     CORAL),
    ("Activation layer",   "build_alerts → ranked, traceable, routed",      TEAL),
    ("Analytical layer",   "commodity_segments / technical_patterns",       TEAL_70),
    ("Data layer",         "cleaned CSVs (Ventas, Clientes, Productos…)",   GREY),
]
y = Inches(1.7)
for title, sub, clr in layers:
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(2.5), y, Inches(8.3), Inches(0.95))
    fill(box, clr); line_no(box)
    add_text(s, Inches(2.85), y + Inches(0.12), Inches(7.7), Inches(0.45),
             title, size=18, bold=True, colour=WHITE, font=H_FONT)
    add_text(s, Inches(2.85), y + Inches(0.52), Inches(7.7), Inches(0.4),
             sub, size=12, colour=WHITE, font=B_FONT)
    # Up arrow between layers
    y_next = y + Inches(0.95) + Inches(0.15)
    if title != "Data layer":
        arr = s.shapes.add_shape(MSO_SHAPE.UP_ARROW,
                                 Inches(6.45), y + Inches(0.95) + Inches(0.05),
                                 Inches(0.4), Inches(0.13))
        fill(arr, CORAL); line_no(arr)
    y = y + Inches(1.15)

# Right side notes
add_text(s, Inches(11.0), Inches(1.7), Inches(2.0), Inches(0.5),
         "Standalone today", size=13, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(11.0), Inches(2.05), Inches(2.0), Inches(0.5),
         "Python module +", size=12, colour=INK, font=B_FONT)
add_text(s, Inches(11.0), Inches(2.30), Inches(2.0), Inches(0.5),
         "Streamlit dashboard", size=12, colour=INK, font=B_FONT)

add_text(s, Inches(11.0), Inches(3.0), Inches(2.0), Inches(0.5),
         "CRM-ready", size=13, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(11.0), Inches(3.35), Inches(2.0), Inches(0.5),
         "HubSpot Tasks", size=12, colour=INK, font=B_FONT)
add_text(s, Inches(11.0), Inches(3.6), Inches(2.0), Inches(0.5),
         "JSON exporter", size=12, colour=INK, font=B_FONT)

add_text(s, Inches(11.0), Inches(4.3), Inches(2.0), Inches(0.5),
         "Idempotent", size=13, bold=True, colour=CORAL, font=H_FONT)
add_text(s, Inches(11.0), Inches(4.65), Inches(2.0), Inches(0.5),
         "generate_alerts(", size=12, colour=INK, font="Consolas")
add_text(s, Inches(11.0), Inches(4.9), Inches(2.0), Inches(0.5),
         "  date)", size=12, colour=INK, font="Consolas")

# ====================================================================
# Slide 9 — Brief scorecard
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "Brief scorecard")
add_text(s, Inches(0.95), Inches(1.15), Inches(11), Inches(0.5),
         "8 of 8 deliverables shipped.",
         size=15, colour=GREY, font=B_FONT)

deliverables = [
    "Purchase-need prediction for commodities",
    "Early churn-risk for technical products",
    "Capture-window identification",
    "Interpretable, actionable alerts",
    "Operational prioritisation",
    "Daily-operation proposal",
    "Standalone-to-CRM evolution path",
    "Learning capability (feedback loop)",
]
cols, rows = 2, 4
cw = Inches(5.95)
ch = Inches(1.05)
for i, txt in enumerate(deliverables):
    c, r = i % cols, i // cols
    x = Inches(0.8 + c * 6.15)
    y = Inches(1.95 + r * 1.20)
    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, ch)
    fill(card, LIGHT); line_no(card)
    # Tick
    tick = s.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(0.3), y + Inches(0.3),
                              Inches(0.45), Inches(0.45))
    fill(tick, CORAL); line_no(tick)
    add_text(s, x + Inches(0.35), y + Inches(0.27), Inches(0.4), Inches(0.5),
             "✓", size=18, bold=True, colour=WHITE, font=H_FONT, align=PP_ALIGN.CENTER)
    add_text(s, x + Inches(0.95), y + Inches(0.32), cw - Inches(1.1), Inches(0.5),
             txt, size=14, colour=INK, font=B_FONT)

# ====================================================================
# Slide 10 — What's next
# ====================================================================
s = prs.slides.add_slide(blank)
slide_title(s, "What's next")

phases = [
    ("Phase 2", "Wire alerts into Inibsa's CRM via the existing HubSpot exporter"),
    ("Phase 2", "Replace mocked outcomes with real recordings from sales team"),
    ("Phase 3", "Threshold auto-tuning when ≥500 real outcomes accumulate"),
    ("Phase 3", "Run a 30-day pilot with control group to measure real lift"),
]
y = Inches(1.85)
for tag, txt in phases:
    pill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(0.8), y, Inches(1.4), Inches(0.55))
    fill(pill, CORAL); line_no(pill)
    add_text(s, Inches(0.8), y + Inches(0.07), Inches(1.4), Inches(0.5),
             tag, size=14, bold=True, colour=WHITE, font=H_FONT, align=PP_ALIGN.CENTER)
    add_text(s, Inches(2.5), y + Inches(0.10), Inches(10.0), Inches(0.6),
             txt, size=16, colour=INK, font=B_FONT)
    y = y + Inches(1.0)

add_text(s, Inches(0.8), Inches(6.5), Inches(12), Inches(0.5),
         "The architecture supports all of this without rewrites.",
         size=14, colour=GREY, font=B_FONT)

# ====================================================================
# Slide 11 — Thank you (dark)
# ====================================================================
s = prs.slides.add_slide(blank)
add_dark_bg(s)
add_circle(s, Inches(6.42), Inches(2.0), Inches(0.5))
add_text(s, Inches(0), Inches(2.8), Inches(13.333), Inches(1.5),
         "Thank you.", size=72, bold=True, colour=WHITE, font=H_FONT,
         align=PP_ALIGN.CENTER)
add_text(s, Inches(0), Inches(4.4), Inches(13.333), Inches(0.7),
         "Smart Demand Signals",
         size=24, colour=CORAL, font=H_FONT, align=PP_ALIGN.CENTER)
add_text(s, Inches(0), Inches(5.1), Inches(13.333), Inches(0.5),
         "github.com/BielMe/hackaton1",
         size=14, colour=RGBColor(0xCA, 0xDC, 0xFC), font="Consolas",
         align=PP_ALIGN.CENTER)

# ---------- Save ----------
out = ROOT / "pitch" / "Smart_Demand_Signals.pptx"
prs.save(out)
print(f"✅ Wrote {out}  ({out.stat().st_size//1024} KB)  ·  {len(prs.slides)} slides")
print(f"   Live numbers used: {NUMS['n_alerts']:,} alerts | {NUMS['n_high']:,} High | "
      f"{fmt_eur(NUMS['total_impact'])}")

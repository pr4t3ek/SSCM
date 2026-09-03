# CIL Lakhanpur Wagon Procurement & Freight Optimization Dashboard

An executive decision-support dashboard for Coal India Limited (CIL) → Mahanadi
Coalfields Limited (MCL) → Lakhanpur OCP, built for an MBA classroom
presentation (SSCM Sec B Team 1). It walks through the team's actual project —
*Optimizing Wagon Procurement & Freight Contracting at CIL (Lakhanpur Area)* —
end to end: what's happening in the shift-wise coal data, where the dispatch
bottleneck is, what it means in rakes, what a Base (captive/leased) vs. Spot
(FOIS) fleet strategy costs, and what CIL should do about it, with a live
What-If Simulator and full scenario/sensitivity analysis.

## Quick start

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**.

For intranet/LAN deployment, set the host to `0.0.0.0` (and optionally a
different port):

```bash
SSCM_HOST=0.0.0.0 SSCM_PORT=5000 python app.py
```

The app is fully self-contained — Plotly.js is vendored locally under
`static/js/vendor/plotly.min.js`, so it runs with no external CDN/internet
dependency once installed.

## What's inside

- **12 MAIN presentation screens** (Executive Summary → Business Problem →
  Demand-Dispatch Gap → Shift Diagnosis → Wagon Requirement → Fleet Strategy →
  Cost Optimization → What-If Simulator → Scenario Comparison → Sensitivity &
  Risk → Final Recommendation → Management Takeaways), reachable from the left
  sidebar and, in **Presentation Mode**, via ← / → keyboard navigation (Esc to
  exit).
- **8 APPENDIX / ANALYTICS pages** (Data Explorer, Detailed Shift Analytics,
  Assumptions & Parameters, Cost Model, Optimization Methodology, Detailed
  Sensitivity, Optimization Output, Data Quality) for the technical detail
  behind every number on the main screens.
- A **transparent optimization engine** (`models/optimization.py`) that finds
  the cost-minimizing Base Fleet Capacity by exact breakpoint search over a
  convex, piecewise-linear cost curve — fast enough to recompute live on every
  What-If Simulator slider drag. The method and its justification are laid out
  in full on Appendix A5.
- Every KPI, chart and insight is **computed live from the dataset** — nothing
  is hard-coded. Illustrative cost parameters (base/spot/demurrage/shortage
  rates) are clearly labeled ASSUMPTION and editable on Appendix A3; the one
  real external figure (rake capacity ≈ 4,000 t) is labeled EXTERNAL, sourced
  from the project proposal.

## Project structure

```
app.py                      Flask app factory / entry point
config.py                   Screen registry + default model parameters
requirements.txt

data/
  raw/                      Source workbook
  lakhanpur_shift_data.csv  Generated clean export (written at startup)

models/                     Pure math: wagon_model, cost_model, optimization
services/                   data_loader, analytics, scenario_engine,
                             optimization_service, insight_generator
routes/                     dashboard (HTML), api (GET JSON), optimization (POST)
templates/                  base.html + one template per screen, appendix/
static/
  css/style.css
  js/                       charts.js, dashboard.js, simulator.js,
                             assumptions-store.js, vendor/plotly.min.js
```

## Data

`Lakhanpur_Area_Shiftwise_Coal_Data.xlsx` (908 shift-level rows, 303 days,
Sept 2025–Jul 2026) is the single source of truth, read once at startup and
cleaned in `services/data_loader.py`. A genuine data-quality issue in the
source file — one shift record with a missing date, leaving one day short a
shift — is surfaced on the Data Quality appendix (A8) rather than silently
dropped or fixed.

## Notes

- No server-side session state: user-edited assumptions live in the browser
  (`localStorage`, via `assumptions-store.js`) and are sent explicitly with
  every optimize/simulate/scenario/sensitivity request.
- Every model-derived figure carries the label *"Model-based result using
  configured assumptions"* to keep observed data, external facts and
  user-editable assumptions clearly distinguished.

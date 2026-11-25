# Stage 2: first SQL analysis tables

`src/build_analysis.py` runs three SQL queries against the stage 1 database
and writes CSVs to `results/`. 27 tests pass (7 new ones recompute every
headline number independently from the raw tables).

```bash
python src/build_analysis.py   # writes results/*.csv
python -m pytest tests/ -q
```

## What was measured and how

- **Revenue** (`results/revenue_by_category.csv`, 74 categories): sum of
  item prices over *delivered* orders only, i.e. goods that actually reached
  the customer. The two untranslated categories keep their Portuguese names
  (`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`); products
  with no category are grouped under `(unknown)`.
- **Delivery** (`results/delivery_performance.csv`, 27 states): calendar
  days from purchase to customer delivery, and the share delivered on or
  before the estimated date, per customer state. Covers the 96,470 delivered
  orders with a recorded delivery date (8 delivered orders have none).
- **Reviews** (`results/review_scores.csv`): score distribution over 99,224
  distinct `(review_id, order_id)` pairs - the source reuses some review IDs
  across orders (see docs/data-pipeline.md), and no pair has conflicting
  scores.

## Headline findings

- Total delivered-item revenue: **R$ 13.22M** across 96,478 delivered
  orders.
- Top categories by revenue: **health_beauty (R$ 1.23M)**, watches_gifts
  (R$ 1.17M), bed_bath_table (R$ 1.02M). High average item prices sit in
  niches like watches_gifts (R$ 199) versus volume categories like
  bed_bath_table (R$ 93 average item price).
- Average delivery takes **12.6 days** overall, and **91.9%** of orders
  arrive on or before the estimated date. SP (the largest state, 40,494
  orders) averages 8.8 days; remote northern states are slowest
  (RR 29.4, AP 27.2, AM 26.4 days).
- Reviews are strongly positive: average score **4.09**, with **57.8%**
  five-star (57,328 reviews, matching the published Kaggle distribution)
  and 11.5% one-star.

## Stage 3 candidates

- Monthly revenue trend and seasonality (2016-2018).
- Freight value share of order value by state.
- Review score vs delivery lateness.

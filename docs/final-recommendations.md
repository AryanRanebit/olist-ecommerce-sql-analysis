# Final findings and recommendations

Summary of what the three analysis stages measured and where an operations
team would act first. Every figure comes from the built tables in
`results/` (96,478 delivered orders, 2016-2018); methods are in
`docs/data-pipeline.md`, `docs/stage2-analysis.md` and
`docs/stage3-time-freight.md`.

## What was measured

- **Revenue**: R$ 13.22M in delivered-item revenue. Top categories:
  health_beauty (R$ 1.23M), watches_gifts (R$ 1.17M), bed_bath_table
  (R$ 1.02M).
- **Trend**: steep growth through 2017 to a Black Friday peak of
  BRL 987,765 in 2017-11 (7,289 orders), then a 2018 plateau of roughly
  BRL 830k-980k per month.
- **Delivery**: 12.6 days on average, 91.9% on or before the estimated
  date. SP averages 8.8 days (94.1% on time); remote northern states are
  slowest: RR 29.4, AP 27.2, AM 26.4 days.
- **Freight**: freight is 12.2% of order value in SP (the largest market,
  40,501 delivered orders) but 21.9% in RR and 19.7% in AM - a nearly
  10-point spread between the cheapest and most expensive state.
- **Reviews**: average 4.09, 57.8% five-star. On-time or early deliveries
  (92.0% of reviews) average 4.29 stars; 3.18 at 1-7 days late; 1.75/1.62
  at 8-14 / 15-30 days late.

## Recommendations

1. **Investigate orders that pass one week late.** In this data the
   average rating drops from 3.18 at 1-7 days late to about 1.6-1.8 at
   8-30 days late. That is an aggregate pattern, not a validated cutoff;
   the practical hypothesis is to prioritise interventions for orders
   already past a week late (proactive updates, escalation) and test
   whether ratings improve.
2. **Focus logistics attention on the remote northern states.** RR, AP,
   AM and AC have the longest average delivery times (29.4, 27.2, 26.4
   and 21.0 days) on small order volumes (41-145 delivered orders), and
   freight costs more relative to order value there (21.9% in RR, 19.7%
   in AM, 18.6% in AC, 17.1% in AP, vs 12.2% in SP). They are the first
   candidates for a carrier review or revised delivery promises. This is
   a customer-state view; these tables do not isolate individual sellers.
3. **Plan November capacity around Black Friday volume.** In 2017-11,
   revenue (BRL 987,765) ran about 44% above the October-December average
   and order count (7,289) about 46% above, while average order value fell
   (BRL 135.51 vs 144.76 in October) - the peak is more orders, not bigger
   baskets, so the strain lands on fulfilment and support.

## Limitations

- The data covers 2016-2018; patterns describe that window, not the
  present market.
- These are associations, not experiments: lateness tracks low review
  scores, but this analysis does not prove that faster delivery raises
  ratings or revenue.
- Revenue and delivery tables cover delivered orders only; reviews are
  counted as distinct (review_id, order_id) pairs.
- Edge months (2016-09, 2016-12, after 2018-08) are dataset-window
  artefacts, not real demand signals.

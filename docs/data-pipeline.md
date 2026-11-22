# Data pipeline: fetch, load, integrity checks

Stage 1 builds the local analysis database from the raw Olist CSVs.
Everything is reproducible with two commands:

```bash
python src/fetch_data.py    # downloads 9 CSVs into data/raw/
python src/build_dataset.py # loads data/processed/olist.db + integrity checks
```

## Source

- Canonical dataset: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle, Version 2), license CC BY-NC-SA 4.0.
- Kaggle downloads require a signed-in Kaggle account, so `fetch_data.py`
  pulls the same nine CSVs from a public GitHub mirror
  (`tunguyenn99/ecommerce-data-modeling`, `dataset/` folder).
- The mirror's content was verified against the canonical dataset before use:
  row counts match the Kaggle version exactly (see below), and the review
  score distribution matches the published one (57,328 five-star reviews).

## Tables loaded into SQLite (`data/processed/olist.db`)

Timestamps are stored as ISO text, matching the source exactly.

| table | rows |
|---|---:|
| customers | 99,441 |
| geolocation | 1,000,163 |
| orders | 99,441 |
| order_items | 112,650 |
| order_payments | 103,886 |
| order_reviews | 99,224 |
| products | 32,951 |
| sellers | 3,095 |
| category_translation | 71 |

## Integrity checks (all passing)

- Row counts match the canonical Kaggle Version 2 counts for all 9 tables.
- `orders.order_id` and `customers.customer_id` are unique.
- Every order references an existing customer.
- Every order item, payment and review references an existing order.
- Every order item references an existing product and seller.
- All review scores are between 1 and 5.
- `order_status` takes only the 8 documented values
  (created, approved, invoiced, processing, shipped, delivered, canceled, unavailable).
- Delivered orders are never delivered before purchase.

## Known data-quality flags (documented, not failures)

- Two product categories have no English translation in
  `category_translation`: `pc_gamer` (9 sold items) and
  `portateis_cozinha_e_preparadores_de_alimentos` (15 sold items). Analysis
  queries should fall back to the Portuguese name for these.
- `order_reviews` has 99,224 rows but only 98,410 distinct `review_id`
  values: the source reuses some review IDs across orders. Deduplicate by
  `(review_id, order_id)` when joining reviews.

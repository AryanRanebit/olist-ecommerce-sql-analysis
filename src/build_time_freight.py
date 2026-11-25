"""Stage 3: time and freight analysis on the Olist SQLite database.

Reads data/processed/olist.db (built by src/build_dataset.py) and writes
three CSVs to results/:

- monthly_revenue_trend.csv    Delivered-order revenue and volume per month.
- freight_share_by_state.csv   Freight share of order value per state.
- review_score_vs_lateness.csv Review scores by delivery-lateness bucket.

Run: python src/build_time_freight.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "olist.db"
RESULTS_DIR = ROOT / "results"

# Revenue and volume per purchase month over delivered orders only, matching
# the delivered-only convention of src/build_analysis.py. Revenue is the sum
# of item prices (freight excluded); the average order value is per distinct
# order. Edge months (2016-09, 2016-12) have a handful of orders because the
# dataset window starts mid-2016; there is no 2016-11 row at all.
MONTHLY_REVENUE_SQL = """
SELECT
    strftime('%Y-%m', o.order_purchase_timestamp) AS month,
    COUNT(DISTINCT o.order_id) AS orders,
    COUNT(*) AS items_sold,
    ROUND(SUM(oi.price), 2) AS revenue_brl,
    ROUND(SUM(oi.price) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value_brl
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id AND o.order_status = 'delivered'
GROUP BY month
ORDER BY month;
"""

# Freight share per customer state over delivered orders: what fraction of
# the total order value (items + freight) went to shipping. Sorted by share
# so remote states with expensive shipping surface first.
FREIGHT_SHARE_SQL = """
SELECT
    c.customer_state AS state,
    COUNT(DISTINCT o.order_id) AS delivered_orders,
    ROUND(SUM(oi.price), 2) AS item_value_brl,
    ROUND(SUM(oi.freight_value), 2) AS freight_brl,
    ROUND(100.0 * SUM(oi.freight_value)
          / (SUM(oi.price) + SUM(oi.freight_value)), 1) AS freight_pct_of_order_value
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id AND o.order_status = 'delivered'
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_state
ORDER BY freight_pct_of_order_value DESC;
"""

# Average review score by how late the delivery was against its estimated
# date. Reviews are deduplicated as distinct (review_id, order_id) pairs,
# the same convention as src/build_analysis.py; an order with more than one
# review contributes each pair once. Timestamps are ISO text, so
# lexicographic comparison with the estimated date is a valid on/before
# check (see src/build_dataset.py). Buckets are fixed and exhaustive, so a
# bucket with zero reviews would still appear (with NULL averages).
LATENESS_SQL = """
WITH pairs AS (
    SELECT DISTINCT review_id, order_id, review_score FROM order_reviews
),
bucketed AS (
    SELECT
        p.review_score,
        CASE
            WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date
                THEN 'on time or early'
            WHEN julianday(o.order_delivered_customer_date)
                 - julianday(o.order_estimated_delivery_date) <= 7
                THEN '1-7 days late'
            WHEN julianday(o.order_delivered_customer_date)
                 - julianday(o.order_estimated_delivery_date) <= 14
                THEN '8-14 days late'
            WHEN julianday(o.order_delivered_customer_date)
                 - julianday(o.order_estimated_delivery_date) <= 30
                THEN '15-30 days late'
            ELSE 'over 30 days late'
        END AS delivery_bucket
    FROM pairs p
    JOIN orders o ON o.order_id = p.order_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
)
SELECT
    delivery_bucket,
    COUNT(*) AS reviews,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_reviews,
    ROUND(AVG(review_score), 2) AS avg_review_score
FROM bucketed
GROUP BY delivery_bucket
ORDER BY CASE delivery_bucket
    WHEN 'on time or early' THEN 0
    WHEN '1-7 days late' THEN 1
    WHEN '8-14 days late' THEN 2
    WHEN '15-30 days late' THEN 3
    ELSE 4
END;
"""

QUERIES = {
    "monthly_revenue_trend.csv": MONTHLY_REVENUE_SQL,
    "freight_share_by_state.csv": FREIGHT_SHARE_SQL,
    "review_score_vs_lateness.csv": LATENESS_SQL,
}


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(
            f"{DB_PATH} missing; run python src/fetch_data.py and "
            "python src/build_dataset.py first."
        )
    RESULTS_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    for filename, sql in QUERIES.items():
        cur = con.execute(sql)
        rows = cur.fetchall()
        out = RESULTS_DIR / filename
        with out.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([d[0] for d in cur.description])
            writer.writerows(rows)
        print(f"{out.relative_to(ROOT)}: {len(rows)} rows")
    con.close()


if __name__ == "__main__":
    main()

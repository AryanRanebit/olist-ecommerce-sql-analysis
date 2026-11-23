"""Stage 2: first SQL analysis tables on the Olist SQLite database.

Reads data/processed/olist.db (built by src/build_dataset.py) and writes
three CSVs to results/:

- revenue_by_category.csv   Revenue per product category, delivered orders.
- delivery_performance.csv  Delivery speed and on-time share per state.
- review_scores.csv         Review score distribution (deduplicated).

Run: python src/build_analysis.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "olist.db"
RESULTS_DIR = ROOT / "results"

# Revenue per product category over delivered orders only: money for goods
# that actually reached the customer. Categories fall back to the Portuguese
# name for the two without an English translation (see docs/data-pipeline.md);
# products with no category at all are grouped under "(unknown)".
REVENUE_BY_CATEGORY_SQL = """
SELECT
    COALESCE(t.product_category_name_english, p.product_category_name, '(unknown)') AS category,
    COUNT(DISTINCT oi.order_id) AS orders,
    COUNT(*) AS items_sold,
    ROUND(SUM(oi.price), 2) AS revenue_brl,
    ROUND(AVG(oi.price), 2) AS avg_item_price_brl
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id AND o.order_status = 'delivered'
JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
GROUP BY category
ORDER BY revenue_brl DESC;
"""

# Delivery speed per customer state, delivered orders with a recorded
# delivery date. Timestamps are ISO text, so lexicographic comparison with
# the estimated date is a valid on/before check (see src/build_dataset.py).
DELIVERY_PERFORMANCE_SQL = """
SELECT
    c.customer_state AS state,
    COUNT(*) AS delivered_orders,
    ROUND(AVG(julianday(o.order_delivered_customer_date)
              - julianday(o.order_purchase_timestamp)), 2) AS avg_delivery_days,
    ROUND(100.0 * SUM(o.order_delivered_customer_date <= o.order_estimated_delivery_date)
          / COUNT(*), 1) AS pct_on_time
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
ORDER BY delivered_orders DESC;
"""

# Review score distribution. The source reuses some review_id values across
# orders, so count distinct (review_id, order_id) pairs, per the data-quality
# note in docs/data-pipeline.md. No pair carries conflicting scores.
REVIEW_SCORES_SQL = """
SELECT
    review_score,
    COUNT(*) AS reviews,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM (SELECT DISTINCT review_id, order_id, review_score FROM order_reviews)
GROUP BY review_score
ORDER BY review_score DESC;
"""

QUERIES = {
    "revenue_by_category.csv": REVENUE_BY_CATEGORY_SQL,
    "delivery_performance.csv": DELIVERY_PERFORMANCE_SQL,
    "review_scores.csv": REVIEW_SCORES_SQL,
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

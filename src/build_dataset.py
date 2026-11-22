"""Load the raw Olist CSVs into a SQLite database and run integrity checks.

Reads data/raw/*.csv and writes data/processed/olist.db with one table per
file. Timestamps stay as ISO text so the database matches the source exactly;
SQL queries can compare them lexicographically. Exits non-zero if any
integrity check fails.
"""

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "processed" / "olist.db"

# table -> (csv file, [(column, SQLite type), ...])
SCHEMA = {
    "customers": ("olist_customers_dataset.csv", [
        ("customer_id", "TEXT"), ("customer_unique_id", "TEXT"),
        ("customer_zip_code_prefix", "INTEGER"), ("customer_city", "TEXT"),
        ("customer_state", "TEXT"),
    ]),
    "geolocation": ("olist_geolocation_dataset.csv", [
        ("geolocation_zip_code_prefix", "INTEGER"), ("geolocation_lat", "REAL"),
        ("geolocation_lng", "REAL"), ("geolocation_city", "TEXT"),
        ("geolocation_state", "TEXT"),
    ]),
    "orders": ("olist_orders_dataset.csv", [
        ("order_id", "TEXT"), ("customer_id", "TEXT"), ("order_status", "TEXT"),
        ("order_purchase_timestamp", "TEXT"), ("order_approved_at", "TEXT"),
        ("order_delivered_carrier_date", "TEXT"),
        ("order_delivered_customer_date", "TEXT"),
        ("order_estimated_delivery_date", "TEXT"),
    ]),
    "order_items": ("olist_order_items_dataset.csv", [
        ("order_id", "TEXT"), ("order_item_id", "INTEGER"),
        ("product_id", "TEXT"), ("seller_id", "TEXT"),
        ("shipping_limit_date", "TEXT"), ("price", "REAL"),
        ("freight_value", "REAL"),
    ]),
    "order_payments": ("olist_order_payments_dataset.csv", [
        ("order_id", "TEXT"), ("payment_sequential", "INTEGER"),
        ("payment_type", "TEXT"), ("payment_installments", "INTEGER"),
        ("payment_value", "REAL"),
    ]),
    "order_reviews": ("olist_order_reviews_dataset.csv", [
        ("review_id", "TEXT"), ("order_id", "TEXT"),
        ("review_score", "INTEGER"), ("review_comment_title", "TEXT"),
        ("review_comment_message", "TEXT"), ("review_creation_date", "TEXT"),
        ("review_answer_timestamp", "TEXT"),
    ]),
    "products": ("olist_products_dataset.csv", [
        ("product_id", "TEXT"), ("product_category_name", "TEXT"),
        ("product_name_lenght", "INTEGER"), ("product_description_lenght", "INTEGER"),
        ("product_photos_qty", "INTEGER"), ("product_weight_g", "REAL"),
        ("product_length_cm", "REAL"), ("product_height_cm", "REAL"),
        ("product_width_cm", "REAL"),
    ]),
    "sellers": ("olist_sellers_dataset.csv", [
        ("seller_id", "TEXT"), ("seller_zip_code_prefix", "INTEGER"),
        ("seller_city", "TEXT"), ("seller_state", "TEXT"),
    ]),
    "category_translation": ("product_category_name_translation.csv", [
        ("product_category_name", "TEXT"),
        ("product_category_name_english", "TEXT"),
    ]),
}

# Canonical row counts of the Olist public dataset (Kaggle Version 2).
EXPECTED_ROWS = {
    "customers": 99_441,
    "geolocation": 1_000_163,
    "orders": 99_441,
    "order_items": 112_650,
    "order_payments": 103_886,
    "order_reviews": 99_224,
    "products": 32_951,
    "sellers": 3_095,
    "category_translation": 71,
}


def convert(value: str, kind: str):
    value = value.strip()
    if value == "":
        return None
    if kind == "INTEGER":
        return int(value)
    if kind == "REAL":
        return float(value)
    return value


def load_table(conn: sqlite3.Connection, table: str) -> int:
    csv_name, columns = SCHEMA[table]
    path = RAW_DIR / csv_name
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run src/fetch_data.py first")
    col_names = [c for c, _ in columns]
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    defs = ", ".join(f"{c} {t}" for c, t in columns)
    conn.execute(f"CREATE TABLE {table} ({defs})")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = [h.strip('"') for h in next(reader)]
        if header != col_names:
            raise ValueError(f"{csv_name}: header {header} != {col_names}")
        batch = []
        count = 0
        insert = f"INSERT INTO {table} VALUES ({','.join('?' * len(columns))})"
        for row in reader:
            batch.append([convert(v, t) for v, (_, t) in zip(row, columns)])
            if len(batch) >= 10_000:
                conn.executemany(insert, batch)
                count += len(batch)
                batch = []
        if batch:
            conn.executemany(insert, batch)
            count += len(batch)
    return count


def integrity_checks(conn: sqlite3.Connection) -> list[str]:
    """Return a list of failure messages; empty means all checks passed."""
    failures = []

    def scalar(sql: str):
        return conn.execute(sql).fetchone()[0]

    for table, expected in EXPECTED_ROWS.items():
        actual = scalar(f"SELECT COUNT(*) FROM {table}")
        if actual != expected:
            failures.append(f"{table}: {actual} rows, expected {expected}")

    if scalar("SELECT COUNT(DISTINCT order_id) FROM orders") != scalar("SELECT COUNT(*) FROM orders"):
        failures.append("orders.order_id is not unique")
    if scalar("SELECT COUNT(DISTINCT customer_id) FROM customers") != scalar("SELECT COUNT(*) FROM customers"):
        failures.append("customers.customer_id is not unique")

    orphans = scalar("""SELECT COUNT(*) FROM orders o
                        LEFT JOIN customers c ON o.customer_id = c.customer_id
                        WHERE c.customer_id IS NULL""")
    if orphans:
        failures.append(f"{orphans} orders reference a missing customer")
    for table in ("order_items", "order_payments", "order_reviews"):
        orphans = scalar(f"""SELECT COUNT(*) FROM {table} t
                             LEFT JOIN orders o ON t.order_id = o.order_id
                             WHERE o.order_id IS NULL""")
        if orphans:
            failures.append(f"{orphans} {table} rows reference a missing order")
    orphans = scalar("""SELECT COUNT(*) FROM order_items i
                        LEFT JOIN products p ON i.product_id = p.product_id
                        WHERE p.product_id IS NULL""")
    if orphans:
        failures.append(f"{orphans} order_items reference a missing product")
    orphans = scalar("""SELECT COUNT(*) FROM order_items i
                        LEFT JOIN sellers s ON i.seller_id = s.seller_id
                        WHERE s.seller_id IS NULL""")
    if orphans:
        failures.append(f"{orphans} order_items reference a missing seller")

    bad = scalar("SELECT COUNT(*) FROM order_reviews WHERE review_score NOT BETWEEN 1 AND 5")
    if bad:
        failures.append(f"{bad} reviews with score outside 1..5")

    return failures


def data_quality_flags(conn: sqlite3.Connection) -> list[str]:
    """Known source-data quirks worth documenting; they do not fail the build."""
    flags = []
    untranslated = [row[0] for row in conn.execute(
        """SELECT DISTINCT p.product_category_name FROM products p
           LEFT JOIN category_translation t
             ON p.product_category_name = t.product_category_name
           WHERE p.product_category_name IS NOT NULL
             AND t.product_category_name IS NULL""")]
    if untranslated:
        flags.append(f"{len(untranslated)} product categories have no English "
                     f"translation: {', '.join(sorted(untranslated))}")
    return flags


def main() -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with conn:
        for table in SCHEMA:
            rows = load_table(conn, table)
            print(f"{table}: loaded {rows:,} rows")
    failures = integrity_checks(conn)
    for msg in data_quality_flags(conn):
        print(f"FLAG {msg}")
    if failures:
        for msg in failures:
            print(f"FAIL {msg}")
        return 1
    print(f"All integrity checks passed. Database at {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

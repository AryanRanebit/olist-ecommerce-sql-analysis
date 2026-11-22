"""Download the Olist Brazilian E-Commerce CSVs into data/raw/.

Canonical source: Kaggle "Brazilian E-Commerce Public Dataset by Olist"
(https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), published by
Olist under the CC BY-NC-SA 4.0 license. Kaggle downloads need a signed-in
Kaggle account, so this script pulls the same nine CSVs from a public
GitHub mirror. Integrity of the download is checked in build_dataset.py
against the canonical row counts (99,441 orders, 112,650 order items, ...).
"""

import csv
import sys
import urllib.request
from pathlib import Path

MIRROR_BASE = (
    "https://raw.githubusercontent.com/tunguyenn99/"
    "ecommerce-data-modeling/main/dataset"
)
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# file name -> first column expected in the header
FILES = {
    "olist_customers_dataset.csv": "customer_id",
    "olist_geolocation_dataset.csv": "geolocation_zip_code_prefix",
    "olist_order_items_dataset.csv": "order_id",
    "olist_order_payments_dataset.csv": "order_id",
    "olist_order_reviews_dataset.csv": "review_id",
    "olist_orders_dataset.csv": "order_id",
    "olist_products_dataset.csv": "product_id",
    "olist_sellers_dataset.csv": "seller_id",
    "product_category_name_translation.csv": "product_category_name",
}


def fetch_one(name: str, expected_first_column: str) -> int:
    """Download one CSV and return its data-row count."""
    url = f"{MIRROR_BASE}/{name}"
    dest = RAW_DIR / name
    urllib.request.urlretrieve(url, dest)
    with open(dest, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = sum(1 for _ in reader)
    if not header or header[0].strip('"') != expected_first_column:
        raise ValueError(f"{name}: unexpected header {header[:1]!r}")
    return rows


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, first_col in FILES.items():
        rows = fetch_one(name, first_col)
        print(f"{name}: {rows:,} data rows")
    print(f"Saved {len(FILES)} files to {RAW_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

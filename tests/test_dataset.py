"""Integrity tests for the built Olist SQLite database.

Run after `python src/fetch_data.py` and `python src/build_dataset.py`.
The whole module is skipped when data/processed/olist.db has not been built.
"""

import sqlite3
from pathlib import Path

import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "olist.db"

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

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="olist.db not built; run src/fetch_data.py then src/build_dataset.py",
)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


def scalar(db, sql):
    return db.execute(sql).fetchone()[0]


@pytest.mark.parametrize("table,expected", EXPECTED_ROWS.items())
def test_row_count(db, table, expected):
    assert scalar(db, f"SELECT COUNT(*) FROM {table}") == expected


def test_order_ids_unique(db):
    assert scalar(db, "SELECT COUNT(DISTINCT order_id) FROM orders") == EXPECTED_ROWS["orders"]


def test_customer_ids_unique(db):
    assert scalar(db, "SELECT COUNT(DISTINCT customer_id) FROM customers") == EXPECTED_ROWS["customers"]


def test_every_order_has_a_customer(db):
    orphans = scalar(db, """SELECT COUNT(*) FROM orders o
                            LEFT JOIN customers c ON o.customer_id = c.customer_id
                            WHERE c.customer_id IS NULL""")
    assert orphans == 0


@pytest.mark.parametrize("table", ["order_items", "order_payments", "order_reviews"])
def test_child_rows_reference_orders(db, table):
    orphans = scalar(db, f"""SELECT COUNT(*) FROM {table} t
                             LEFT JOIN orders o ON t.order_id = o.order_id
                             WHERE o.order_id IS NULL""")
    assert orphans == 0


def test_items_reference_products_and_sellers(db):
    missing_products = scalar(db, """SELECT COUNT(*) FROM order_items i
                                     LEFT JOIN products p ON i.product_id = p.product_id
                                     WHERE p.product_id IS NULL""")
    missing_sellers = scalar(db, """SELECT COUNT(*) FROM order_items i
                                    LEFT JOIN sellers s ON i.seller_id = s.seller_id
                                    WHERE s.seller_id IS NULL""")
    assert missing_products == 0
    assert missing_sellers == 0


def test_review_scores_in_range(db):
    assert scalar(db, "SELECT COUNT(*) FROM order_reviews WHERE review_score NOT BETWEEN 1 AND 5") == 0


def test_order_status_known_values(db):
    statuses = {row[0] for row in db.execute("SELECT DISTINCT order_status FROM orders")}
    assert statuses == {
        "created", "approved", "invoiced", "processing", "shipped",
        "delivered", "canceled", "unavailable",
    }


def test_delivered_orders_have_sane_dates(db):
    bad = scalar(db, """SELECT COUNT(*) FROM orders
                        WHERE order_status = 'delivered'
                          AND order_delivered_customer_date < order_purchase_timestamp""")
    assert bad == 0


def test_untranslated_categories_are_only_the_two_known_ones(db):
    """Data-quality flag: the source ships two categories with no translation."""
    untranslated = {row[0] for row in db.execute(
        """SELECT DISTINCT p.product_category_name FROM products p
           LEFT JOIN category_translation t
             ON p.product_category_name = t.product_category_name
           WHERE p.product_category_name IS NOT NULL
             AND t.product_category_name IS NULL""")}
    assert untranslated == {"pc_gamer", "portateis_cozinha_e_preparadores_de_alimentos"}

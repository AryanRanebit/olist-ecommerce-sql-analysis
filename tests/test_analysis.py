"""Independent checks for the stage 2 analysis tables in results/.

Run after `python src/build_analysis.py`. Every expected value here is
recomputed from the database in plain Python, not by re-running the
analysis SQL. The whole module is skipped when results/ has not been built.
"""

import csv
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "olist.db"
RESULTS = ROOT / "results"
REVENUE_CSV = RESULTS / "revenue_by_category.csv"
DELIVERY_CSV = RESULTS / "delivery_performance.csv"
REVIEWS_CSV = RESULTS / "review_scores.csv"

pytestmark = pytest.mark.skipif(
    not (DB_PATH.exists() and REVENUE_CSV.exists()
         and DELIVERY_CSV.exists() and REVIEWS_CSV.exists()),
    reason="run src/build_analysis.py first (needs the stage 1 database)",
)


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# --- revenue_by_category.csv ------------------------------------------------

def python_revenue_totals(db):
    """Delivered-order revenue per category, recomputed row by row."""
    translated = dict(db.execute(
        "SELECT product_category_name, product_category_name_english "
        "FROM category_translation"))
    category_of = dict(db.execute(
        "SELECT product_id, product_category_name FROM products"))
    delivered = {row[0] for row in db.execute(
        "SELECT order_id FROM orders WHERE order_status = 'delivered'")}
    totals = defaultdict(float)
    for order_id, product_id, price in db.execute(
            "SELECT order_id, product_id, price FROM order_items"):
        if order_id not in delivered:
            continue
        raw = category_of.get(product_id)
        category = translated.get(raw, raw) or "(unknown)"
        totals[category] += price
    return totals


def test_revenue_totals_match_independent_sum(db):
    expected = python_revenue_totals(db)
    rows = read_csv(REVENUE_CSV)
    assert len(rows) == len(expected)
    assert abs(sum(float(r["revenue_brl"]) for r in rows)
               - sum(expected.values())) < 0.01
    by_category = {r["category"]: float(r["revenue_brl"]) for r in rows}
    for category, revenue in expected.items():
        assert abs(by_category[category] - revenue) < 0.01


def test_revenue_untranslated_and_unknown_categories_present():
    rows = read_csv(REVENUE_CSV)
    categories = {r["category"] for r in rows}
    # The two categories with no English translation fall back to Portuguese.
    assert "pc_gamer" in categories
    assert "portateis_cozinha_e_preparadores_de_alimentos" in categories
    # Products with no category at all are grouped under "(unknown)".
    assert "(unknown)" in categories
    # Every row is internally consistent.
    for r in rows:
        assert int(r["orders"]) >= 1
        assert int(r["items_sold"]) >= int(r["orders"])
        assert float(r["revenue_brl"]) > 0


def test_revenue_sorted_descending():
    revenues = [float(r["revenue_brl"]) for r in read_csv(REVENUE_CSV)]
    assert revenues == sorted(revenues, reverse=True)


# --- delivery_performance.csv -----------------------------------------------

def python_delivery_stats(db):
    """Per-state delivery days and on-time share, recomputed from raw rows."""
    state_of = dict(db.execute(
        "SELECT customer_id, customer_state FROM customers"))
    days_by_state = defaultdict(list)
    on_time_by_state = defaultdict(int)
    for (customer_id, purchase, delivered, estimated) in db.execute(
            "SELECT customer_id, order_purchase_timestamp, "
            "order_delivered_customer_date, order_estimated_delivery_date "
            "FROM orders WHERE order_status = 'delivered' "
            "AND order_delivered_customer_date IS NOT NULL"):
        state = state_of[customer_id]
        fmt = "%Y-%m-%d %H:%M:%S"
        days = (datetime.fromisoformat(delivered)
                - datetime.fromisoformat(purchase)).total_seconds() / 86400
        days_by_state[state].append(days)
        # ISO text compares lexicographically, same as the analysis SQL.
        if delivered <= estimated:
            on_time_by_state[state] += 1
    return {
        state: (len(days), sum(days) / len(days),
                100.0 * on_time_by_state[state] / len(days))
        for state, days in days_by_state.items()
    }


def test_delivery_rows_cover_all_delivered_orders(db):
    expected_orders = db.execute(
        "SELECT COUNT(*) FROM orders WHERE order_status = 'delivered' "
        "AND order_delivered_customer_date IS NOT NULL").fetchone()[0]
    rows = read_csv(DELIVERY_CSV)
    assert sum(int(r["delivered_orders"]) for r in rows) == expected_orders


def test_delivery_stats_match_independent_recompute(db):
    expected = python_delivery_stats(db)
    rows = read_csv(DELIVERY_CSV)
    assert len(rows) == len(expected) == 27  # 26 Brazilian states + DF
    for r in rows:
        count, avg_days, pct_on_time = expected[r["state"]]
        assert int(r["delivered_orders"]) == count
        assert abs(float(r["avg_delivery_days"]) - avg_days) < 0.01
        assert abs(float(r["pct_on_time"]) - pct_on_time) < 0.1
        assert 0 <= float(r["avg_delivery_days"]) <= 60
        assert 0 <= float(r["pct_on_time"]) <= 100


# --- review_scores.csv -------------------------------------------------------

def test_review_scores_match_deduped_pairs(db):
    # Distinct (review_id, order_id) pairs: the source reuses review_id
    # values across orders, and no pair carries conflicting scores.
    pair_score = {}
    for review_id, order_id, score in db.execute(
            "SELECT review_id, order_id, review_score FROM order_reviews"):
        pair_score[(review_id, order_id)] = score
    expected_counts = defaultdict(int)
    for score in pair_score.values():
        expected_counts[score] += 1

    rows = read_csv(REVIEWS_CSV)
    assert {int(r["review_score"]) for r in rows} == {1, 2, 3, 4, 5}
    total = sum(expected_counts.values())
    assert sum(int(r["reviews"]) for r in rows) == total == len(pair_score)
    for r in rows:
        score = int(r["review_score"])
        assert int(r["reviews"]) == expected_counts[score]
        assert abs(float(r["pct"])
                   - 100.0 * expected_counts[score] / total) < 0.01
    assert abs(sum(float(r["pct"]) for r in rows) - 100.0) < 0.05


def test_review_five_star_count_matches_published_figure():
    # The Kaggle Version 2 review distribution has 57,328 five-star reviews
    # (see docs/data-pipeline.md).
    rows = {int(r["review_score"]): int(r["reviews"])
            for r in read_csv(REVIEWS_CSV)}
    assert rows[5] == 57_328

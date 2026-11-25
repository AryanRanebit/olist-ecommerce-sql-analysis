"""Independent checks for the stage 3 time/freight tables in results/.

Run after `python src/build_time_freight.py`. Every expected value here is
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
MONTHLY_CSV = RESULTS / "monthly_revenue_trend.csv"
FREIGHT_CSV = RESULTS / "freight_share_by_state.csv"
LATENESS_CSV = RESULTS / "review_score_vs_lateness.csv"

pytestmark = pytest.mark.skipif(
    not (DB_PATH.exists() and MONTHLY_CSV.exists()
         and FREIGHT_CSV.exists() and LATENESS_CSV.exists()),
    reason="run src/build_time_freight.py first (needs the stage 1 database)",
)

BUCKET_ORDER = [
    "on time or early",
    "1-7 days late",
    "8-14 days late",
    "15-30 days late",
    "over 30 days late",
]


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def parse(ts):
    return datetime.fromisoformat(ts)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


def delivered_orders(db):
    """order_id -> (purchase, delivered, estimated, state) for delivered rows."""
    states = dict(db.execute("SELECT customer_id, customer_state FROM customers"))
    out = {}
    for row in db.execute(
            "SELECT order_id, customer_id, order_purchase_timestamp, "
            "order_delivered_customer_date, order_estimated_delivery_date "
            "FROM orders WHERE order_status = 'delivered'"):
        order_id, customer_id, purchased, delivered, estimated = row
        out[order_id] = (purchased, delivered, estimated, states[customer_id])
    return out


# --- monthly_revenue_trend.csv ----------------------------------------------

def python_monthly(db):
    """Per-month delivered-order totals, recomputed row by row."""
    orders = delivered_orders(db)
    months = defaultdict(lambda: {"orders": set(), "items": 0, "revenue": 0.0})
    for order_id, price in db.execute(
            "SELECT order_id, price FROM order_items"):
        if order_id not in orders:
            continue
        month = orders[order_id][0][:7]  # ISO text, first 7 chars = YYYY-MM
        agg = months[month]
        agg["orders"].add(order_id)
        agg["items"] += 1
        agg["revenue"] += price
    return months


def test_monthly_every_row_matches_independent_totals(db):
    expected = python_monthly(db)
    rows = read_csv(MONTHLY_CSV)
    assert {r["month"] for r in rows} == set(expected)
    for r in rows:
        agg = expected[r["month"]]
        assert int(r["orders"]) == len(agg["orders"])
        assert int(r["items_sold"]) == agg["items"]
        assert abs(float(r["revenue_brl"]) - agg["revenue"]) < 0.01


def test_months_in_chronological_order():
    months = [r["month"] for r in read_csv(MONTHLY_CSV)]
    assert months == sorted(months)
    for m in months:
        datetime.strptime(m, "%Y-%m")  # parses as a real month


def test_monthly_revenue_sums_to_delivered_item_total(db):
    csv_total = sum(float(r["revenue_brl"]) for r in read_csv(MONTHLY_CSV))
    delivered = {row[0] for row in db.execute(
        "SELECT order_id FROM orders WHERE order_status = 'delivered'")}
    db_total = sum(price for order_id, price in db.execute(
        "SELECT order_id, price FROM order_items") if order_id in delivered)
    assert abs(csv_total - db_total) < 0.01


def test_avg_order_value_is_revenue_over_orders():
    for r in read_csv(MONTHLY_CSV):
        expected = float(r["revenue_brl"]) / int(r["orders"])
        assert abs(float(r["avg_order_value_brl"]) - expected) < 0.01


def test_items_sold_at_least_orders():
    for r in read_csv(MONTHLY_CSV):
        assert int(r["items_sold"]) >= int(r["orders"])


# --- freight_share_by_state.csv ----------------------------------------------

def python_freight(db):
    """Per-state item/freight totals over delivered orders, recomputed."""
    orders = delivered_orders(db)
    states = defaultdict(lambda: {"orders": set(), "price": 0.0, "freight": 0.0})
    for order_id, price, freight in db.execute(
            "SELECT order_id, price, freight_value FROM order_items"):
        if order_id not in orders:
            continue
        agg = states[orders[order_id][3]]
        agg["orders"].add(order_id)
        agg["price"] += price
        agg["freight"] += freight
    return states


def test_freight_every_row_matches_independent_totals(db):
    expected = python_freight(db)
    rows = read_csv(FREIGHT_CSV)
    assert {r["state"] for r in rows} == set(expected)
    for r in rows:
        agg = expected[r["state"]]
        assert int(r["delivered_orders"]) == len(agg["orders"])
        assert abs(float(r["item_value_brl"]) - agg["price"]) < 0.01
        assert abs(float(r["freight_brl"]) - agg["freight"]) < 0.01


def test_freight_covers_every_customer_state(db):
    all_states = {row[0] for row in db.execute(
        "SELECT DISTINCT customer_state FROM customers")}
    assert {r["state"] for r in read_csv(FREIGHT_CSV)} == all_states


def test_freight_pct_consistent_with_value_columns():
    for r in read_csv(FREIGHT_CSV):
        freight = float(r["freight_brl"])
        total = freight + float(r["item_value_brl"])
        assert abs(float(r["freight_pct_of_order_value"])
                   - 100.0 * freight / total) < 0.05


def test_freight_pct_bounds_and_sorting():
    pcts = [float(r["freight_pct_of_order_value"])
            for r in read_csv(FREIGHT_CSV)]
    assert all(0 < p < 100 for p in pcts)
    assert pcts == sorted(pcts, reverse=True)


# --- review_score_vs_lateness.csv --------------------------------------------

def python_lateness(db):
    """Per-bucket review scores, recomputed from deduplicated pairs."""
    orders = delivered_orders(db)
    scores = defaultdict(list)
    for review_id, order_id, score in db.execute(
            "SELECT DISTINCT review_id, order_id, review_score "
            "FROM order_reviews"):
        if order_id not in orders:
            continue
        _, delivered, estimated, _ = orders[order_id]
        if delivered is None:
            continue
        # Exact lateness in days, matching the SQL julianday difference.
        late_days = (parse(delivered) - parse(estimated)).total_seconds() / 86400
        if delivered <= estimated:  # lexicographic, as in the analysis SQL
            bucket = "on time or early"
        elif late_days <= 7:
            bucket = "1-7 days late"
        elif late_days <= 14:
            bucket = "8-14 days late"
        elif late_days <= 30:
            bucket = "15-30 days late"
        else:
            bucket = "over 30 days late"
        scores[bucket].append(score)
    return scores


def test_lateness_bucket_set_and_fixed_order():
    rows = read_csv(LATENESS_CSV)
    assert [r["delivery_bucket"] for r in rows] == BUCKET_ORDER


def test_lateness_counts_and_scores_match_independent_run(db):
    expected = python_lateness(db)
    rows = read_csv(LATENESS_CSV)
    assert {r["delivery_bucket"] for r in rows} == set(expected)
    for r in rows:
        scores = expected[r["delivery_bucket"]]
        assert int(r["reviews"]) == len(scores)
        assert abs(float(r["avg_review_score"])
                   - sum(scores) / len(scores)) < 0.01


def test_lateness_pct_of_reviews_sums_to_100():
    total = sum(float(r["pct_of_reviews"])
                for r in read_csv(LATENESS_CSV))
    assert abs(total - 100.0) < 0.05


def test_avg_scores_within_review_scale():
    for r in read_csv(LATENESS_CSV):
        assert 1.0 <= float(r["avg_review_score"]) <= 5.0


def test_on_time_reviews_score_above_every_late_bucket():
    rows = {r["delivery_bucket"]: float(r["avg_review_score"])
            for r in read_csv(LATENESS_CSV)}
    on_time = rows["on time or early"]
    for bucket in BUCKET_ORDER[1:]:
        assert on_time > rows[bucket]

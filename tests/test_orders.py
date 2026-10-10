"""Orders, delivery fee and revenue rules. Created rows are removed (see conftest.py)."""

import pytest

from app import db as database
from app import orders, sales
from app.catalog import StoreError


def _customer(**extra):
    data = {
        "buyer": "pytest buyer",
        "phone": "0612345678",
        "address": "rue 1",
        "city": "Fès",
    }
    data.update(extra)
    return data


# ---------------------------------------------------------------- delivery
@pytest.mark.parametrize("city", ["BHALIL", "bhalil", " Bhalil ", "البهاليل", "بهاليل"])
def test_delivery_is_free_in_bhalil(city):
    assert orders.delivery_fee(100, city) == 0


def test_bhalil_is_always_written_in_capitals():
    assert orders.normalize_city("bhalil") == "BHALIL"
    assert orders.normalize_city("بهاليل") == "البهاليل"
    assert orders.normalize_city("fès") == "fès"


@pytest.mark.parametrize(("subtotal", "fee"), [(100, 40), (499.99, 40), (500, 0), (900, 0)])
def test_delivery_fee_elsewhere(subtotal, fee):
    assert orders.delivery_fee(subtotal, "Fès") == fee


def test_no_city_means_no_delivery():
    assert orders.delivery_fee(100, "") == 0


# ------------------------------------------------------------ public orders
def test_public_order_uses_catalog_prices(product):
    item = {"id": product["id"], "name": product["name"], "size": "0.5kg", "qty": 2, "price": 0.01}
    result = orders.create_order(_customer(items=[item]))
    assert result["status"] == "pending"
    assert result["items"][0]["price"] == 50.0  # browser price ignored
    assert result["subtotal"] == 100.0
    assert result["delivery_fee"] == 40
    assert result["total"] == 140.0


def test_public_order_requires_delivery_details(product):
    item = {"id": product["id"], "size": "1kg", "qty": 1}
    for missing in ("buyer", "phone", "address", "city"):
        with pytest.raises(StoreError):
            orders.create_order(_customer(items=[item], **{missing: ""}))


def test_unknown_product_or_size_is_refused(product):
    with pytest.raises(StoreError) as err:
        orders.create_order(_customer(items=[{"id": "nope", "name": "nope", "qty": 1}]))
    assert err.value.code == "product_unavailable"
    with pytest.raises(StoreError) as err:
        orders.create_order(_customer(items=[{"id": product["id"], "size": "9kg", "qty": 1}]))
    assert err.value.code == "invalid_size"


# -------------------------------------------------- confirmation & revenue
def _month_revenue():
    return sales.sales_summary()["month"]["revenue"]


def test_only_confirmed_orders_count_in_revenue(product):
    before = _month_revenue()
    item = {"id": product["id"], "size": "1kg", "qty": 1}
    order = orders.create_order(_customer(items=[item], city="BHALIL"))
    assert _month_revenue() == before  # pending: not counted

    orders.confirm_order(order["order_id"])
    assert _month_revenue() == pytest.approx(before + 100.0)
    with database.live_db() as conn:
        row = conn.execute(
            "SELECT confirmed_at FROM orders WHERE id=?", (order["order_id"],)
        ).fetchone()
    assert row["confirmed_at"][:7] == database.current_month()


def test_rejected_order_is_deleted(product):
    order = orders.create_order(_customer(items=[{"id": product["id"], "size": "1kg", "qty": 1}]))
    orders.reject_order(order["order_id"])
    with database.live_db() as conn:
        assert not conn.execute("SELECT 1 FROM orders WHERE id=?", (order["order_id"],)).fetchone()
        assert not conn.execute(
            "SELECT 1 FROM order_items WHERE order_id=?", (order["order_id"],)
        ).fetchone()


def test_confirmed_order_cannot_be_rejected(product):
    order = orders.create_order(_customer(items=[{"id": product["id"], "size": "1kg", "qty": 1}]))
    orders.confirm_order(order["order_id"])
    with pytest.raises(StoreError):
        orders.reject_order(order["order_id"])


def test_manual_order_is_confirmed_and_needs_a_category(category):
    before = _month_revenue()
    item = {"name": "in-shop sale", "price": 75, "qty": 2, "cat": category["slug"]}
    result = orders.create_order({"buyer": "walk-in", "items": [item]}, manual=True)
    assert result["status"] == "confirmed"
    assert result["delivery_fee"] == 0
    assert _month_revenue() == pytest.approx(before + 150.0)

    with pytest.raises(StoreError) as err:
        orders.create_order({"buyer": "x", "items": [dict(item, cat="")]}, manual=True)
    assert err.value.code == "invalid_category"


def test_list_orders_filters_by_date(product):
    order = orders.create_order(_customer(items=[{"id": product["id"], "size": "1kg", "qty": 1}]))
    today = database.now()[:10]
    ids = {o["id"] for o in orders.list_orders(today, today)}
    assert order["order_id"] in ids
    assert order["order_id"] not in {
        o["id"] for o in orders.list_orders("2000-01-01", "2000-01-31")
    }


# -------------------------------------------------------------- best sellers
def _sell(product, qty, confirm=True, confirmed_at=None):
    order = orders.create_order(_customer(items=[{"id": product["id"], "size": "1kg", "qty": qty}]))
    if confirm:
        orders.confirm_order(order["order_id"])
    if confirmed_at:  # back-date this test's own order
        with database.live_db() as conn:
            conn.execute(
                "UPDATE orders SET confirmed_at=? WHERE id=?", (confirmed_at, order["order_id"])
            )
    return order


def _best_ids():
    from app import catalog

    with database.live_db() as conn:
        return [p["id"] for p in catalog.featured_from_sales(conn, limit=50)]


def test_best_sellers_are_the_most_ordered_products(category):
    from app import catalog

    big = catalog.add_product("pytest-big-seller", category["slug"], 10.0, "")
    small = catalog.add_product("pytest-small-seller", category["slug"], 10.0, "")
    _sell(big, 50, confirmed_at="2000-01-01T10:00:00")  # old sales still count
    _sell(small, 2)
    ids = _best_ids()
    assert ids.index(big["id"]) < ids.index(small["id"])


def test_pending_orders_do_not_make_best_sellers(category):
    from app import catalog

    p = catalog.add_product("pytest-pending-only", category["slug"], 10.0, "")
    _sell(p, 99, confirm=False)
    assert p["id"] not in _best_ids()

import time
from app import db, catalog

def test_grouped_catalog_has_seeded_categories():
    data = catalog.grouped_catalog()
    assert "categories" in data and "featured" in data
    ids = {c["id"] for c in data["categories"]}
    assert {"amlou", "miels", "huiles"}.issubset(ids)

def test_create_and_update_product(tmp_path=None):
    # use real DB, cleanup after
    cat_name = f"TestCat {int(time.time())}"
    cat = catalog.create_category(cat_name)
    assert cat["slug"].startswith("c")
    prod = catalog.add_product("ProdTest", cat["slug"], 123.45, "")
    assert prod["id"].startswith("p")
    updated = catalog.update_product(prod["id"], name="ProdTest Renamed", price= 999)
    assert updated["name"] == "ProdTest Renamed"
    assert updated["min"] == 999
    # cleanup
    catalog.delete_product(prod["id"])
    # category stays (enterprise keeps history) – not deleted

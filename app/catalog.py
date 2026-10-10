"""Catalog domain logic: products, categories, archive, best sellers and media."""

import base64
import functools
import json
import os
import re
import secrets
import time

from . import config
from . import db as database


class StoreError(Exception):
    """Application-level error that maps to a JSON API response."""

    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra


# Version of the public catalog. Every write that changes what
# GET /api/v1/catalog returns bumps it, so the HTTP layer can serve a cached
# copy in between (the catalog is read on every page view, written rarely).
_catalog_version = [0]


def bump_catalog_version():
    _catalog_version[0] += 1


def catalog_version():
    return _catalog_version[0]


def _changes_catalog(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            bump_catalog_version()

    return wrapper


def barcode():
    return f"p{int(time.time() * 1000)}{secrets.token_hex(3)}"


def is_liquid(cat):
    """Oils (huiles) are measured in litres; every other category defaults to kg."""
    return cat in config.LIQUID_CATEGORIES


def default_sizes(cat, price):
    """Size variants used when the admin did not define any.

    Regular products default to 1 kg / 0.5 kg (the smaller one costs half).
    Oils default to 1 L / 5 L (price scales linearly from the per-unit price).
    Products without a price have no variants (shown as "price on request").
    """
    if price is None:
        return []
    base = round(float(price), 2)
    if is_liquid(cat):
        return [
            {"size": "1", "unit": "L", "price": base},
            {"size": "5", "unit": "L", "price": round(base * 5, 2)},
        ]
    return [
        {"size": "1", "unit": "kg", "price": base},
        {"size": "0.5", "unit": "kg", "price": round(base / 2, 2)},
    ]


def _stored_sizes(raw):
    """Decode the JSON `sizes` column; returns a list or None when unset/invalid."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, list) or not data:
        return None
    return data


def parse_sizes(raw):
    """Validate/normalize a sizes payload coming from the API.

    Returns ``None`` when the field is absent (unchanged) and a (possibly
    empty) list otherwise. Raises StoreError on malformed input.
    """
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise StoreError(400, "invalid_sizes", "صيغة الأحجام غير صالحة")
    if len(raw) > config.MAX_SIZES:
        raise StoreError(400, "invalid_sizes", f"عدد الأحجام كبير جداً (الحد {config.MAX_SIZES})")
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise StoreError(400, "invalid_sizes", "صيغة الحجم غير صالحة")
        size = str(item.get("size", "")).strip()
        unit = str(item.get("unit", "")).strip()
        if not size or len(size) > 12:
            raise StoreError(400, "invalid_sizes", "قيمة الحجم غير صالحة (1 إلى 12 حرفاً)")
        if unit not in config.SIZE_UNITS:
            raise StoreError(400, "invalid_sizes", "الوحدة غير صالحة (kg أو L)")
        try:
            price = round(float(item.get("price")), 2)
        except (TypeError, ValueError):
            raise StoreError(400, "invalid_sizes", "سعر الحجم غير صالح") from None
        if not (0 <= price <= 1_000_000):
            raise StoreError(400, "invalid_sizes", "سعر الحجم غير صالح")
        key = (size.casefold(), unit)
        if key in seen:
            continue
        seen.add(key)
        out.append({"size": size, "unit": unit, "price": price})
    return out


def _dump_sizes(sizes):
    return json.dumps(sizes, ensure_ascii=False) if sizes else None


def product_sizes(row):
    """Effective sizes for a product row: admin-defined ones, else the defaults."""
    stored = _stored_sizes(row["sizes"]) if "sizes" in row.keys() else None
    if stored:
        return stored
    return default_sizes(row["cat"], row["min"])


def size_label(size):
    """Human label of a size variant, identical to the storefront's (e.g. ``0.5kg``)."""
    return f"{size['size']}{size['unit']}"


def _clean_description(text):
    text = (text or "").strip()
    if len(text) > config.MAX_DESCRIPTION_LEN:
        raise StoreError(
            400, "invalid_description", f"الوصف طويل جداً (الحد {config.MAX_DESCRIPTION_LEN} حرف)"
        )
    return text


def product_json(row):
    keys = row.keys()
    return {
        "id": row["id"],
        "name": row["name"],
        "cat": row["cat"],
        "min": row["min"],
        "max": row["max"],
        "img": row["img"],
        "ribbon": bool(row["ribbon"]),
        "featured": bool(row["featured"]),
        "custom": bool(row["custom"]),
        "sizes": product_sizes(row),
        # True when the sizes were set by the admin (not derived from the price)
        "sizes_custom": bool(_stored_sizes(row["sizes"]) if "sizes" in keys else None),
        "description": (row["description"] if "description" in keys else None) or "",
    }


def category_json(row):
    return {
        "slug": row["slug"],
        "title_ar": row["title_ar"],
        "title_fr": row["title_fr"],
        "title_en": row["title_en"],
        "img": row["img"],
    }


# ---------------------------------------------------------------------------
# catalog assembly
# ---------------------------------------------------------------------------


def featured_from_sales(conn, limit=4):
    """'Best sellers' = the products ordered the most (units, all time).

    Only confirmed orders count. Until enough products have sales, the
    catalog's ``featured`` picks fill the remaining slots.
    """
    sold = conn.execute(
        "SELECT oi.product_id, oi.product_name, oi.cat FROM order_items oi"
        " JOIN orders o ON o.id = oi.order_id"
        " WHERE o.status = 'confirmed'"
        " GROUP BY COALESCE(oi.product_id, oi.product_name || '|' || oi.cat)"
        " ORDER BY SUM(oi.qty) DESC, MAX(o.confirmed_at) DESC"
    ).fetchall()
    featured, seen = [], set()

    def take(row):
        if row and row["id"] not in seen and len(featured) < limit:
            seen.add(row["id"])
            featured.append(product_json(row))

    for r in sold:
        row = None
        if r["product_id"]:
            row = conn.execute("SELECT * FROM products WHERE id=?", (r["product_id"],)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM products WHERE name=? AND cat=? ORDER BY custom DESC LIMIT 1",
                (r["product_name"], r["cat"]),
            ).fetchone()
        take(row)
    for row in conn.execute("SELECT * FROM products WHERE featured=1 ORDER BY rowid"):
        take(row)
    return featured


def grouped_catalog():
    with database.live_db() as conn:
        cats = conn.execute("SELECT * FROM categories ORDER BY rowid").fetchall()
        prods = conn.execute("SELECT * FROM products ORDER BY rowid").fetchall()
        out = []
        for c in cats:
            out.append(
                {
                    "id": c["slug"],
                    "title_ar": c["title_ar"],
                    "title_fr": c["title_fr"],
                    "title_en": c["title_en"],
                    "img": c["img"],
                    "products": [product_json(r) for r in prods if r["cat"] == c["slug"]],
                }
            )
        featured = featured_from_sales(conn)
    return {"categories": out, "featured": featured}


def category_names():
    """slug -> Arabic title, including archived categories (used by reports)."""
    names = {}
    with database.archive_db() as conn:
        for r in conn.execute("SELECT slug,title_ar FROM old_categories ORDER BY archived_at"):
            names[r["slug"]] = r["title_ar"]
    with database.live_db() as conn:
        for r in conn.execute("SELECT slug,title_ar FROM categories"):
            names[r["slug"]] = r["title_ar"]
    return names


# ---------------------------------------------------------------------------
# categories
# ---------------------------------------------------------------------------


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def get_category(conn, slug):
    return conn.execute("SELECT * FROM categories WHERE slug=?", (slug,)).fetchone()


def find_category_by_name(conn, name):
    """Return the category whose any title matches `name` (case/space tolerant)."""
    needle = normalize(name)
    for row in conn.execute("SELECT * FROM categories").fetchall():
        for key in ("title_ar", "title_fr", "title_en"):
            if normalize(row[key]) == needle:
                return row
    return None


def category_exists(conn, slug):
    return conn.execute("SELECT 1 FROM categories WHERE slug=?", (slug,)).fetchone() is not None


@_changes_catalog
def create_category(name):
    name = re.sub(r"\s+", " ", (name or "")).strip()
    if not (2 <= len(name) <= config.MAX_CATEGORY_NAME_LEN):
        raise StoreError(
            400,
            "invalid_category_name",
            f"اسم الفئة يجب أن يكون بين 2 و {config.MAX_CATEGORY_NAME_LEN} حرفاً",
        )
    with database.db_lock, database.live_db() as conn:
        existing = find_category_by_name(conn, name)
        if existing:
            raise StoreError(409, "category_exists", "هذه الفئة موجودة مسبقاً", id=existing["slug"])
        slug = "c" + secrets.token_hex(5)
        conn.execute(
            "INSERT INTO categories(slug,title_ar,title_fr,title_en,img) VALUES(?,?,?,?,?)",
            (slug, name, name, name, config.P + "cat-default.svg"),
        )
        row = get_category(conn, slug)
    return category_json(row)


@_changes_catalog
def delete_category(slug, archived_by="admin"):
    """Move an empty category to the archive database."""
    slug = (slug or "").strip()
    if not slug:
        raise StoreError(400, "invalid_category", "فئة غير صالحة")
    with database.db_lock, database.live_db() as conn:
        row = get_category(conn, slug)
        if not row:
            raise StoreError(404, "not_found", "الفئة غير موجودة")
        cnt = conn.execute("SELECT COUNT(*) AS c FROM products WHERE cat=?", (slug,)).fetchone()[
            "c"
        ]
        if cnt:
            raise StoreError(
                400,
                "category_has_products",
                "لا يمكن حذف فئة تحتوي على منتجات — احذف منتجاتها أولاً.",
            )
        with database.archive_db() as arch:
            arch.execute(
                "INSERT INTO old_categories"
                "(id,slug,title_ar,title_fr,title_en,img,archived_at,archived_by)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (
                    database.unique_id("oc"),
                    row["slug"],
                    row["title_ar"],
                    row["title_fr"],
                    row["title_en"],
                    row["img"],
                    database.now(),
                    archived_by,
                ),
            )
        conn.execute("DELETE FROM categories WHERE slug=?", (slug,))
    return {"deleted": slug, "archived": True}


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------


def _check_name(name):
    name = (name or "").strip()
    if not (1 <= len(name) <= config.MAX_NAME_LEN):
        raise StoreError(
            400,
            "invalid_product_name",
            f"اسم المنتج مطلوب (الحد {config.MAX_NAME_LEN} حرفاً)",
        )
    return name


@_changes_catalog
def add_product(name, cat, price, img_source, sizes=None, description=""):
    name = _check_name(name)
    if price is not None and not (0 <= price <= 1_000_000):
        raise StoreError(400, "invalid_price", "السعر غير صالح")
    sizes = parse_sizes(sizes)
    description = _clean_description(description)
    if not sizes and price is None:
        raise StoreError(400, "invalid_price", "السعر أو الأحجام مطلوبة")

    min_price, max_price = price, None
    if sizes:
        min_price = min(s["price"] for s in sizes)
        max_price = max(s["price"] for s in sizes)

    with database.db_lock, database.live_db() as conn:
        if not category_exists(conn, cat):
            raise StoreError(400, "invalid_category", "الفئة غير موجودة")
        if conn.execute("SELECT 1 FROM products WHERE name=? AND cat=?", (name, cat)).fetchone():
            raise StoreError(409, "product_exists", "يوجد منتج بنفس الاسم في هذه الفئة")
        stored_img = store_image_source(img_source) if img_source else ""
        pid = barcode()
        conn.execute(
            "INSERT INTO products"
            " (id,name,cat,min,max,img,ribbon,featured,custom,created,sizes,description)"
            " VALUES(?,?,?,?,?,?,0,0,1,?,?,?)",
            (
                pid,
                name,
                cat,
                min_price,
                max_price,
                stored_img,
                database.now(),
                _dump_sizes(sizes),
                description,
            ),
        )
        row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    return product_json(row)


@_changes_catalog
def update_product(
    pid, name=None, cat=None, price=None, img_source=None, sizes=None, description=None
):
    """Update an existing product. ``None`` means "unchanged" for every field.

    Pricing rules (identical to ``add_product``):
    - explicit sizes  -> min/max come from the sizes, ``price`` is ignored;
    - ``sizes == []`` -> custom sizes are cleared, defaults derive from ``price``.
    """
    if name is not None:
        name = _check_name(name)
    if cat is not None:
        cat = (cat or "").strip()
        if not cat:
            raise StoreError(400, "invalid_category", "الفئة غير موجودة")
    if price == "":
        price = None
    elif price is not None:
        try:
            price = round(float(price), 2)
        except (TypeError, ValueError):
            raise StoreError(400, "invalid_price", "السعر غير صالح") from None
        if not (0 <= price <= 1_000_000):
            raise StoreError(400, "invalid_price", "السعر غير صالح")
    sizes = parse_sizes(sizes)
    if description is not None:
        description = _clean_description(description)

    need_img = bool(img_source)
    stored_img = store_image_source(img_source) if need_img else None

    with database.db_lock, database.live_db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if not row:
            raise StoreError(404, "not_found", "المنتج غير موجود")
        new_name = name if name is not None else row["name"]
        new_cat = cat if cat is not None else row["cat"]
        new_img = stored_img if need_img else row["img"]
        new_desc = description if description is not None else row["description"]

        size_json, new_min, new_max = row["sizes"], row["min"], row["max"]
        if sizes:
            size_json = _dump_sizes(sizes)
            new_min = min(s["price"] for s in sizes)
            new_max = max(s["price"] for s in sizes)
        else:
            if sizes == []:
                size_json = None
            if price is not None and not _stored_sizes(size_json):
                new_min, new_max = price, None

        if cat is not None and not category_exists(conn, new_cat):
            raise StoreError(400, "invalid_category", "الفئة غير موجودة")
        if (new_name != row["name"] or new_cat != row["cat"]) and conn.execute(
            "SELECT 1 FROM products WHERE name=? AND cat=? AND id<>? LIMIT 1",
            (new_name, new_cat, pid),
        ).fetchone():
            raise StoreError(409, "product_exists", "يوجد منتج بنفس الاسم في هذه الفئة")

        old_img = row["img"]
        conn.execute(
            "UPDATE products SET name=?, cat=?, min=?, max=?, img=?, sizes=?, description=?"
            " WHERE id=?",
            (new_name, new_cat, new_min, new_max, new_img, size_json, new_desc, pid),
        )
        updated = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if need_img and old_img and old_img != new_img:
        remove_stored_image(old_img)
    return product_json(updated)


@_changes_catalog
def archive_product(pid, archived_by):
    """Delete a product from the catalog by moving it to the archive database.

    The full row (and its image file) is kept so the product can be restored.
    """
    with database.db_lock, database.live_db() as live_conn:
        row = live_conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if not row:
            raise StoreError(404, "not_found", "المنتج غير موجود")
        rev_id = database.unique_id("old")
        with database.archive_db() as archive_conn:
            archive_conn.execute(
                "INSERT INTO old_products"
                " (id,original_id,name,cat,min,max,img,ribbon,featured,custom,"
                " created,revoked_at,revoked_by,sizes,description)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rev_id,
                    row["id"],
                    row["name"],
                    row["cat"],
                    row["min"],
                    row["max"],
                    row["img"],
                    row["ribbon"],
                    row["featured"],
                    row["custom"],
                    row["created"],
                    database.now(),
                    archived_by,
                    row["sizes"],
                    row["description"],
                ),
            )
        live_conn.execute("DELETE FROM products WHERE id=?", (pid,))
    return rev_id


# Legacy names: both former actions now archive.
revoke_product = archive_product


def delete_product(pid, archived_by="admin"):
    return archive_product(pid, archived_by)


def list_archive():
    with database.archive_db() as conn:
        products = [
            dict(r)
            for r in conn.execute(
                "SELECT id,original_id,name,cat,min,img,revoked_at,revoked_by FROM old_products"
                " ORDER BY revoked_at DESC"
            )
        ]
        categories = [
            dict(r)
            for r in conn.execute(
                "SELECT id,slug,title_ar,archived_at,archived_by FROM old_categories"
                " ORDER BY archived_at DESC"
            )
        ]
    return {"products": products, "categories": categories}


@_changes_catalog
def restore_product(archive_id):
    """Put an archived product back into the catalog (re-creating its category)."""
    with database.db_lock, database.archive_db() as arch:
        row = arch.execute("SELECT * FROM old_products WHERE id=?", (archive_id,)).fetchone()
        if not row:
            raise StoreError(404, "not_found", "المنتج غير موجود في الأرشيف")
        with database.live_db() as conn:
            if not category_exists(conn, row["cat"]):
                cat = arch.execute(
                    "SELECT * FROM old_categories WHERE slug=? ORDER BY archived_at DESC LIMIT 1",
                    (row["cat"],),
                ).fetchone()
                if not cat:
                    raise StoreError(400, "invalid_category", "فئة هذا المنتج لم تعد موجودة")
                conn.execute(
                    "INSERT INTO categories(slug,title_ar,title_fr,title_en,img) VALUES(?,?,?,?,?)",
                    (cat["slug"], cat["title_ar"], cat["title_fr"], cat["title_en"], cat["img"]),
                )
                arch.execute("DELETE FROM old_categories WHERE slug=?", (cat["slug"],))
            if conn.execute(
                "SELECT 1 FROM products WHERE name=? AND cat=?", (row["name"], row["cat"])
            ).fetchone():
                raise StoreError(409, "product_exists", "يوجد منتج بنفس الاسم في هذه الفئة")
            pid = row["original_id"]
            if not pid or conn.execute("SELECT 1 FROM products WHERE id=?", (pid,)).fetchone():
                pid = barcode()
            conn.execute(
                "INSERT INTO products"
                " (id,name,cat,min,max,img,ribbon,featured,custom,created,sizes,description)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    pid,
                    row["name"],
                    row["cat"],
                    row["min"],
                    row["max"],
                    row["img"],
                    row["ribbon"],
                    row["featured"],
                    row["custom"],
                    row["created"],
                    row["sizes"],
                    row["description"],
                ),
            )
        arch.execute("DELETE FROM old_products WHERE id=?", (archive_id,))
    return {"restored": pid}


# ---------------------------------------------------------------------------
# media (uploaded product images)
# ---------------------------------------------------------------------------

IMAGE_URL_RE = re.compile(r"^assets/[A-Za-z0-9_./-]+$")
UPLOAD_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def sniff_ext(content):
    """Return the image type from its magic bytes (raster formats only)."""
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:3] == b"\xff\xd8\xff":
        return "jpg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content[:5] in (b"GIF87", b"GIF89"):
        return "gif"
    return None


def store_image_source(source):
    """Accept either a data-URL (uploaded file) or a known local asset path."""
    if source.startswith("data:"):
        _, sep, data = source.partition(",")
        if not sep:
            raise StoreError(400, "invalid_image", "صورة غير صالحة")
        try:
            content = base64.b64decode(data.strip(), validate=True)
        except Exception:
            raise StoreError(400, "invalid_image", "صورة غير صالحة") from None
        if not content or len(content) > config.MAX_UPLOAD_BYTES:
            raise StoreError(400, "invalid_image", "الصورة كبيرة جداً (الحد 8 ميغا)")
        ext = sniff_ext(content)
        if not ext:
            raise StoreError(400, "invalid_image", "صيغة الصورة غير مدعومة (PNG، JPG، WEBP، GIF)")
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        fname = f"prod_{int(time.time() * 1000)}{secrets.token_hex(3)}.{ext}"
        with open(os.path.join(config.UPLOAD_DIR, fname), "wb") as fh:
            fh.write(content)
        return config.UPLOAD_URL_PREFIX + fname
    if IMAGE_URL_RE.match(source or "") and ".." not in source:
        return source
    raise StoreError(400, "invalid_image", "مصدر الصورة غير مسموح")


def uploaded_file_path(rel_path):
    """Filesystem path of an uploaded image URL, or None if it is not one."""
    if not rel_path or not rel_path.startswith(config.UPLOAD_URL_PREFIX):
        return None
    name = rel_path[len(config.UPLOAD_URL_PREFIX) :]
    if not UPLOAD_NAME_RE.match(name):
        return None
    return os.path.join(config.UPLOAD_DIR, name)


def remove_stored_image(rel_path):
    full = uploaded_file_path(rel_path)
    if full and os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass

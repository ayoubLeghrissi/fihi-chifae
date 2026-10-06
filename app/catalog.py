"""Catalog domain logic: products, categories, sales-driven featured and media."""

import base64
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


def barcode(time_like=None):
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
        raise StoreError(400, "invalid_sizes", "formats de taille invalides")
    if len(raw) > config.MAX_SIZES:
        raise StoreError(400, "invalid_sizes", f"trop de tailles (max {config.MAX_SIZES} unités)")
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise StoreError(400, "invalid_sizes", "format de taille invalide")
        size = str(item.get("size", "")).strip()
        unit = str(item.get("unit", "")).strip()
        if not size or len(size) > 12:
            raise StoreError(400, "invalid_sizes", "taille invalide (1 à 12 caractères)")
        if unit not in config.SIZE_UNITS:
            raise StoreError(400, "invalid_sizes", "unité invalide (kg ou L)")
        try:
            price = round(float(item.get("price")), 2)
        except (TypeError, ValueError):
            raise StoreError(400, "invalid_sizes", "prix de taille invalide") from None
        if not (0 <= price <= 1_000_000):
            raise StoreError(400, "invalid_sizes", "prix de taille invalide")
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
    keys = row.keys()
    stored = _stored_sizes(row["sizes"]) if "sizes" in keys else None
    if stored:
        return stored
    return default_sizes(row["cat"], row["min"])


def product_json(row):
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
    """'Best sellers' = the products actually sold the most (from order_items).

    Falls back to the seeded `featured` picks until enough real sales exist.
    """
    sold = conn.execute(
        "SELECT product_name, cat FROM order_items"
        " GROUP BY product_name, cat"
        " ORDER BY SUM(qty) DESC, MAX(created) DESC"
    ).fetchall()
    featured, seen = [], set()
    for r in sold:
        row = conn.execute(
            "SELECT * FROM products WHERE name=? AND cat=? ORDER BY custom DESC LIMIT 1",
            (r["product_name"], r["cat"]),
        ).fetchone()
        if not row:
            continue
        pj = product_json(row)
        if pj["name"] in seen:
            continue
        seen.add(pj["name"])
        featured.append(pj)
        if len(featured) >= limit:
            break
    if len(featured) < limit:
        for row in conn.execute(
            "SELECT * FROM products WHERE featured=1 ORDER BY rowid"
        ).fetchall():
            pj = product_json(row)
            if pj["name"] in seen:
                continue
            seen.add(pj["name"])
            featured.append(pj)
            if len(featured) >= limit:
                break
    return featured


def grouped_catalog():
    with database.db() as conn:
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


def create_category(name):
    name = re.sub(r"\s+", " ", (name or "")).strip()
    if not (2 <= len(name) <= config.MAX_CATEGORY_NAME_LEN):
        raise StoreError(
            400,
            "invalid_category_name",
            f"le nom de la catégorie doit faire entre 2 et "
            f"{config.MAX_CATEGORY_NAME_LEN} caractères",
        )
    with database.db_lock:
        with database.db() as conn:
            existing = find_category_by_name(conn, name)
            if existing:
                raise StoreError(
                    409, "category_exists", "cette catégorie existe déjà", id=existing["slug"]
                )
            slug = "c" + secrets.token_hex(5)
            conn.execute(
                "INSERT INTO categories(slug,title_ar,title_fr,title_en,img)" " VALUES(?,?,?,?,?)",
                (slug, name, name, name, config.P + "cat-default.svg"),
            )
            row = get_category(conn, slug)
    return category_json(row)


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------


def add_product(name, cat, price, img_source, sizes=None):
    name = (name or "").strip()
    if not (1 <= len(name) <= config.MAX_NAME_LEN):
        raise StoreError(
            400,
            "invalid_product_name",
            f"le nom du produit est obligatoire (max {config.MAX_NAME_LEN} caractères)",
        )
    if price is not None and not (0 <= price <= 1_000_000):
        raise StoreError(400, "invalid_price", "prix invalide")
    sizes = parse_sizes(sizes)
    if sizes is not None and not sizes and price is None:
        raise StoreError(400, "invalid_price", "prix ou tailles requis")

    if price is None and sizes:
        price = min(s["price"] for s in sizes)
    max_price = max((s["price"] for s in sizes), default=None) if sizes else None

    with database.db_lock:
        with database.db() as conn:
            if not category_exists(conn, cat):
                raise StoreError(400, "invalid_category", "catégorie inconnue")
            if conn.execute(
                "SELECT 1 FROM products WHERE name=? AND cat=? AND custom=1", (name, cat)
            ).fetchone():
                raise StoreError(409, "product_exists", "un produit identique existe déjà")

            stored_img = store_image_source(img_source) if img_source else ""
            pid = barcode()
            now = database._now()
            conn.execute(
                "INSERT INTO products"
                " (id,name,cat,min,max,img,ribbon,featured,custom,created,sizes)"
                " VALUES(?,?,?,?,?,?,0,0,1,?,?)",
                (pid, name, cat, price, max_price, stored_img, now, _dump_sizes(sizes)),
            )
    return {
        "id": pid,
        "name": name,
        "price": price,
        "cat": cat,
        "img": stored_img,
        "sizes": sizes or default_sizes(cat, price),
    }


def update_product(pid, name=None, cat=None, price=None, img_source=None, sizes=None):
    """Mettre à jour un produit existant (nom, prix, catégorie, image, tailles)."""
    # Normalisation / validation des champs fournis (None = inchangé)
    if name is not None:
        name = (name or "").strip()
        if not (1 <= len(name) <= config.MAX_NAME_LEN):
            raise StoreError(
                400,
                "invalid_product_name",
                f"le nom du produit est obligatoire (max {config.MAX_NAME_LEN} caractères)",
            )
    if cat is not None:
        cat = (cat or "").strip()
        if not cat:
            raise StoreError(400, "invalid_category", "catégorie inconnue")
    if price is not None and price != "":
        try:
            price = round(float(price), 2)
        except (TypeError, ValueError):
            raise StoreError(400, "invalid_price", "prix invalide") from None
        if not (0 <= price <= 1_000_000):
            raise StoreError(400, "invalid_price", "prix invalide")
    elif price == "":
        price = None
    sizes = parse_sizes(sizes)

    # img_source: None = inchangé, "" = conserver, sinon data: ou assets/
    stored_img = None
    need_img = img_source is not None and img_source != ""
    if need_img:
        stored_img = store_image_source(img_source)

    with database.db_lock:
        with database.db() as conn:
            row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if not row:
                raise StoreError(404, "not_found", "produit introuvable")
            new_name = name if name is not None else row["name"]
            new_cat = cat if cat is not None else row["cat"]
            new_img = stored_img if need_img else row["img"]

            # tailles: None = inchangé ; [] = retour aux tailles par défaut
            size_json = row["sizes"]
            new_min = row["min"]
            new_max = row["max"]
            if sizes is not None:
                size_json = _dump_sizes(sizes)
                if sizes:
                    new_min = min(s["price"] for s in sizes)
                    new_max = max(s["price"] for s in sizes)
            if price is not None:
                new_min = price

            # catégorie doit exister si changée
            if cat is not None and not category_exists(conn, new_cat):
                raise StoreError(400, "invalid_category", "catégorie inconnue")

            # éviter doublon nom+cat pour un autre produit custom
            if new_name != row["name"] or new_cat != row["cat"]:
                dup = conn.execute(
                    "SELECT 1 FROM products WHERE name=? AND cat=? AND id<>? LIMIT 1",
                    (new_name, new_cat, pid),
                ).fetchone()
                # on bloque seulement si l'autre occupe déjà le même nom/cat
                if dup:
                    # si le doublon est custom, 409 ; sinon on autorise mais on prévient ?
                    raise StoreError(
                        409,
                        "product_exists",
                        "un produit avec ce nom existe déjà dans cette catégorie",
                    )

            old_img = row["img"]
            conn.execute(
                "UPDATE products SET name=?, cat=?, min=?, max=?, img=?, sizes=? WHERE id=?",
                (new_name, new_cat, new_min, new_max, new_img, size_json, pid),
            )
            updated = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    # nettoyage ancien fichier si remplacé
    if need_img and old_img and old_img != new_img:
        remove_stored_image(old_img)
    return product_json(updated)


def delete_product(pid):
    with database.db_lock:
        with database.db() as conn:
            row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if not row:
                raise StoreError(404, "not_found", "produit introuvable")
            if not row["custom"]:
                raise StoreError(
                    403,
                    "protected_product",
                    "seul un produit ajouté par l'admin peut être supprimé définitivement",
                )
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
    remove_stored_image(row["img"])
    return True


def revoke_product(pid, revoked_by):
    """Move a product out of the active catalog into `old_products`.

    The original row data is preserved (including the image file) so the
    product can be restored later without losing anything.
    """
    with database.db_lock:
        with database.db() as conn:
            row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if not row:
                raise StoreError(404, "not_found", "produit introuvable")
            rev_id = f"old{int(time.time() * 1000)}{secrets.token_hex(3)}"
            conn.execute(
                "INSERT INTO old_products"
                " (id,original_id,name,cat,min,max,img,ribbon,featured,custom,"
                " created,revoked_at,revoked_by,sizes)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    database._now(),
                    revoked_by,
                    row["sizes"],
                ),
            )
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
    return rev_id


# ---------------------------------------------------------------------------
# media (uploaded product images)
# ---------------------------------------------------------------------------

IMAGE_URL_RE = re.compile(r"^assets/[A-Za-z0-9_./-]+$")


def sniff_ext(content):
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b"WEBP" in content[:12]:
        return "webp"
    if content[:5] in (b"GIF87", b"GIF89"):
        return "gif"
    if content[:5] in (b"<?xml", b"<svg ") or b"<svg" in content[:200]:
        return "svg"
    return None


def store_image_source(source):
    """Accept either a data-URL (uploaded file) or a known local asset path."""
    if source.startswith("data:"):
        _, sep, data = source.partition(",")
        if not sep:
            raise StoreError(400, "invalid_image", "image invalide")
        try:
            content = base64.b64decode(data.strip(), validate=True)
        except Exception:
            raise StoreError(400, "invalid_image", "image invalide") from None
        if not content or len(content) > config.MAX_UPLOAD_BYTES:
            raise StoreError(400, "invalid_image", "image trop lourde (8 Mo max)")
        ext = sniff_ext(content)
        if not ext:
            raise StoreError(400, "invalid_image", "format d'image non reconnu")
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        fname = f"prod_{int(time.time() * 1000)}{secrets.token_hex(3)}.{ext}"
        with open(os.path.join(config.UPLOAD_DIR, fname), "wb") as fh:
            fh.write(content)
        return "assets/uploads/" + fname
    if IMAGE_URL_RE.match(source or ""):
        return source
    raise StoreError(400, "invalid_image", "source d'image non autorisée")


def remove_stored_image(rel_path):
    if not rel_path or not rel_path.startswith("assets/uploads/"):
        return
    full = os.path.join(config.BASE, *rel_path.split("/"))
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass


def delete_category(slug):
    slug = (slug or "").strip()
    if not slug:
        raise StoreError(400, "invalid_category", "catégorie invalide")
    with database.db_lock:
        with database.db() as conn:
            row = get_category(conn, slug)
            if not row:
                raise StoreError(404, "not_found", "catégorie introuvable")
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM products WHERE cat=?", (slug,)
            ).fetchone()["c"]
            if cnt:
                raise StoreError(
                    400,
                    "category_has_products",
                    "impossible de supprimer une catégorie contenant des produits",
                )
            conn.execute("DELETE FROM categories WHERE slug=?", (slug,))
    return {"deleted": slug}


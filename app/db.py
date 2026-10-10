"""SQLite persistence: schema, migrations, seeds, sessions and admin credentials.

Two databases are used:

- the *live* database holds everything the shop works with (catalog, orders,
  admin account, sessions, newsletter subscribers);
- the *archive* database keeps deleted products and categories.

Both files live in ``config.DATA_DIR`` (a persistent volume in production).
"""

import datetime
import io
import os
import secrets
import shutil
import sqlite3
import threading
import tempfile
import time
import zipfile
import zoneinfo

from . import config
from .security import hash_password, hash_token, verify_password

_lock = threading.RLock()
# Public name so other modules can serialize compound write transactions.
db_lock = _lock

_TZ = zoneinfo.ZoneInfo(config.TIMEZONE)

# ---------------------------------------------------------------------------
# Database connections
# ---------------------------------------------------------------------------


def _connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def live_db():
    """Connection to the live database (active data)."""
    return _connect(config.DB_FILE)


def archive_db():
    """Connection to the archive database (deleted products/categories)."""
    return _connect(config.ARCHIVE_DB_FILE)


# Backward compatibility - default to the live database.
db = live_db


# ---------------------------------------------------------------------------
# time helpers (shop local time, Morocco)
# ---------------------------------------------------------------------------


def now():
    """Current shop-local timestamp, ``YYYY-MM-DDTHH:MM:SS``."""
    return datetime.datetime.now(_TZ).strftime("%Y-%m-%dT%H:%M:%S")


def current_month():
    return datetime.datetime.now(_TZ).strftime("%Y-%m")


_now = now  # legacy alias


# ---------------------------------------------------------------------------
# demo catalog (only inserted when FIHI_SEED_DEMO=1, e.g. for local previews)
# ---------------------------------------------------------------------------

SEED_CATEGORIES = [
    ("amlou", "أملو", "Amlou", "Amlou", config.P + "prod-amlou.svg"),
    ("miels", "العسل", "Miel", "Honey", config.P + "prod-miel.svg"),
    ("huiles", "الزيوت", "Huiles", "Oils", config.P + "cat-argan.svg"),
    ("cosmetiques", "عطور", "Parfums", "Perfumes", config.P + "cat-promo.svg"),
    ("autres", "منتوجات أخرى", "Autres produits", "Other products", config.P + "prod-pack.svg"),
    ("recettes", "وصفات فيه شفاء", "Recettes", "Recipes", config.P + "prod-coffret.svg"),
    ("packs", "باقات فيه شفاء", "Packs", "Packs", config.P + "prod-pack.svg"),
    ("thes", "الشاي", "Thés", "Teas", config.P + "story.svg"),
]

# (id, name, cat, min, max, img, ribbon, featured)
SEED_PRODUCTS = [
    ("s-amlou-01", "أملو بالكاوكاو وزيت الزيتون والعسل", "amlou", 95, None, None, 0, 0),
    ("s-amlou-02", "أملو باللوز وزيت أركان والعسل الحر", "amlou", 109, 239, None, 1, 1),
    ("s-amlou-03", "أملو باللوز وزيت الزيتون والعسل", "amlou", 99, 189, None, 0, 0),
    ("s-miels-01", "عسل السدر", "miels", 350, None, config.P + "prod1.jpg", 0, 0),
    ("s-miels-02", "عسل الأكالبتوس الحر", "miels", 350, None, config.P + "prod2.jpg", 0, 1),
    ("s-miels-03", "عسل الزعتر الحر", "miels", 350, None, config.P + "prod3.jpg", 0, 0),
    ("s-miels-04", "عسل الخروب الحر", "miels", 350, None, config.P + "prod4.jpg", 0, 0),
    ("s-miels-05", "عسل الزكوم الحر", "miels", 350, None, config.P + "prod5.jpg", 0, 0),
    ("s-huiles-01", "زيت أركان للتجميل", "huiles", 75, None, None, 0, 0),
    ("s-huiles-02", "زيت أركان للأكل", "huiles", 250, None, None, 0, 0),
    ("s-huiles-03", "زيت الزيتون", "huiles", 140, None, None, 0, 0),
    ("s-huiles-04", "زيت الخروع", "huiles", 80, None, None, 0, 0),
    ("s-huiles-05", "زيت اللوز الحلو", "huiles", 25, None, None, 0, 0),
    ("s-huiles-06", "زيت اللوز المر", "huiles", 25, None, None, 0, 0),
    ("s-huiles-07", "زيت الأزير", "huiles", 50, None, None, 0, 0),
    ("s-huiles-08", "زيت السمسم", "huiles", 35, None, None, 0, 0),
    ("s-huiles-09", "زيت القنب الهندي", "huiles", 65, None, None, 0, 0),
    ("s-cosm-01", "صابونة الأركان", "cosmetiques", 50, None, None, 0, 0),
    ("s-cosm-02", "كريم الشيا", "cosmetiques", 50, None, None, 0, 0),
    ("s-cosm-03", "غاسول بالورد", "cosmetiques", 60, None, None, 0, 0),
    ("s-cosm-04", "ماسك الطين الأخضر", "cosmetiques", 35, None, None, 0, 0),
    ("s-cosm-05", "تونر ماء الورد", "cosmetiques", 45, None, None, 0, 0),
    ("s-cosm-06", "سكراب الشفاه بالعسل", "cosmetiques", 28, 35, None, 0, 0),
    ("s-autr-01", "سلو رويال", "autres", 100, 150, None, 0, 0),
    ("s-autr-02", "الجيسينك بودرة", "autres", None, None, None, 0, 0),
    ("s-autr-03", "العكبر الخام", "autres", None, None, None, 0, 0),
    ("s-autr-04", "حبوب اللقاح", "autres", None, None, None, 0, 0),
    ("s-autr-05", "خل التفاح", "autres", 35, None, None, 0, 0),
    ("s-autr-06", "الجيسينغ شرائح", "autres", 140, None, None, 0, 0),
    ("s-autr-07", "العكبر البلدي بودرة", "autres", 70, None, None, 0, 0),
    ("s-autr-08", "ليبطون", "autres", 35, None, None, 0, 0),
    ("s-reci-01", "وجبة الطاقة", "recettes", 220, 749, None, 1, 1),
    ("s-reci-02", "وصفة الجهاز الهضمي", "recettes", 100, 360, None, 0, 0),
    ("s-reci-03", "الوصفة المقوية", "recettes", 99, 580, None, 0, 0),
    ("s-reci-04", "الوصفة الملكية 👑", "recettes", 99, 590, None, 1, 0),
    ("s-pack-01", "باقة رمضان", "packs", 449, 689, None, 1, 1),
    ("s-pack-02", "باقة عيد الأضحى المبارك", "packs", 590, None, None, 0, 0),
    ("s-thes-01", "علي المقام", "thes", None, None, None, 0, 0),
    ("s-thes-02", "كشمير", "thes", None, None, None, 0, 0),
    ("s-thes-03", "جبل علي", "thes", 80, None, None, 0, 0),
    ("s-thes-04", "شاي الحاكم", "thes", 105, None, None, 0, 0),
    ("s-thes-05", "المقام الذهبي", "thes", 105, None, None, 0, 0),
]

CAT_IMG = {c[0]: c[4] for c in SEED_CATEGORIES}

# Live database schema (active data)
LIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS categories(
    slug TEXT PRIMARY KEY,
    title_ar TEXT, title_fr TEXT, title_en TEXT,
    img TEXT
);
CREATE TABLE IF NOT EXISTS products(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cat TEXT NOT NULL,
    min REAL, max REAL,
    img TEXT,
    ribbon INTEGER DEFAULT 0,
    featured INTEGER DEFAULT 0,
    custom INTEGER DEFAULT 0,
    created TEXT,
    sizes TEXT,
    description TEXT
);
CREATE TABLE IF NOT EXISTS orders(
    id TEXT PRIMARY KEY,
    buyer TEXT,
    phone TEXT,
    address TEXT,
    city TEXT,
    location TEXT,
    created TEXT,
    status TEXT DEFAULT 'pending',
    confirmed_at TEXT,
    delivery_fee REAL DEFAULT 0,
    source TEXT DEFAULT 'online'
);
CREATE TABLE IF NOT EXISTS order_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    product_id TEXT,
    product_name TEXT,
    cat TEXT,
    price REAL,
    qty INTEGER,
    created TEXT,
    size TEXT
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE TABLE IF NOT EXISTS password_resets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL,
    email TEXT,
    created INTEGER NOT NULL,
    expires INTEGER NOT NULL,
    used INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions(
    token_hash TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    ip TEXT,
    created INTEGER NOT NULL,
    expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS newsletter(
    email TEXT PRIMARY KEY,
    lang TEXT,
    created TEXT
);
"""

# Archive database schema (deleted products and categories)
ARCHIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS old_products(
    id TEXT PRIMARY KEY,
    original_id TEXT,
    name TEXT, cat TEXT,
    min REAL, max REAL,
    img TEXT,
    ribbon INTEGER DEFAULT 0,
    featured INTEGER DEFAULT 0,
    custom INTEGER DEFAULT 0,
    created TEXT,
    revoked_at TEXT,
    revoked_by TEXT,
    sizes TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS idx_old_products_original ON old_products(original_id);
CREATE TABLE IF NOT EXISTS old_categories(
    id TEXT PRIMARY KEY,
    slug TEXT,
    title_ar TEXT, title_fr TEXT, title_en TEXT,
    img TEXT,
    archived_at TEXT,
    archived_by TEXT
);
"""

# Categories whose display name is brand-consistent and must stay in sync
# with previously-seeded databases.
CATEGORY_NAME_UPDATES = [
    ("recettes", "وصفات فيه شفاء", "Recettes", "Recipes"),
    ("packs", "باقات فيه شفاء", "Packs", "Packs"),
    ("cosmetiques", "عطور", "Parfums", "Perfumes"),
]


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))


def unique_id(prefix):
    return f"{prefix}{int(time.time() * 1000)}{secrets.token_hex(3)}"


def _ensure_column(conn, table, column, decl):
    """Add a column to an existing table when missing (SQLite has no IF NOT EXISTS)."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _ensure_data_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    probe = os.path.join(config.DATA_DIR, ".write-test")
    try:
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
    except OSError as exc:
        raise SystemExit(
            f"[db] data directory {config.DATA_DIR} is not writable ({exc}). "
            "Mount a volume there and make it writable (Railway: set RAILWAY_RUN_UID=0)."
        ) from exc


def _migrate_legacy_uploads():
    """Copy images uploaded before the data volume existed into it (once)."""
    src, dst = config.LEGACY_UPLOAD_DIR, config.UPLOAD_DIR
    if os.path.abspath(src) == os.path.abspath(dst) or not os.path.isdir(src):
        return
    copied = 0
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if name.startswith(".") or not os.path.isfile(s) or os.path.exists(d):
            continue
        shutil.copy2(s, d)
        copied += 1
    if copied:
        print(f"[db] copied {copied} uploaded image(s) into {dst}")


def init_db():
    """Create/migrate the schema and seed the reference catalog."""
    _ensure_data_dir()

    # One-time migration of the old database filename.
    legacy = os.path.join(config.BASE, "dhenbio.db")
    if not os.path.exists(config.DB_FILE) and os.path.exists(legacy):
        os.replace(legacy, config.DB_FILE)
        print(f"[db] migrated legacy database -> {config.DB_FILE}")

    with _lock:
        with live_db() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(LIVE_SCHEMA)
            # migrations for databases created by older releases
            _ensure_column(conn, "products", "sizes", "TEXT")
            _ensure_column(conn, "products", "description", "TEXT")
            _ensure_column(conn, "order_items", "size", "TEXT")
            _ensure_column(conn, "order_items", "product_id", "TEXT")
            _ensure_column(conn, "orders", "status", "TEXT DEFAULT 'pending'")
            _ensure_column(conn, "orders", "address", "TEXT")
            _ensure_column(conn, "orders", "city", "TEXT")
            _ensure_column(conn, "orders", "location", "TEXT")
            _ensure_column(conn, "orders", "confirmed_at", "TEXT")
            _ensure_column(conn, "orders", "delivery_fee", "REAL DEFAULT 0")
            _ensure_column(conn, "orders", "source", "TEXT DEFAULT 'online'")
            # orders confirmed before confirmation dates were recorded
            conn.execute(
                "UPDATE orders SET confirmed_at=created"
                " WHERE status='confirmed' AND confirmed_at IS NULL"
            )

            # demo catalog only on request (a real shop starts empty)
            if config.SEED_DEMO and not get_meta(conn, "seeded"):
                conn.executemany(
                    "INSERT OR REPLACE INTO categories(slug,title_ar,title_fr,title_en,img)"
                    " VALUES(?,?,?,?,?)",
                    SEED_CATEGORIES,
                )
                ts = now()
                conn.executemany(
                    "INSERT OR REPLACE INTO products"
                    " (id,name,cat,min,max,img,ribbon,featured,custom,created)"
                    " VALUES(?,?,?,?,?,?,?,?,0,?)",
                    [
                        (p[0], p[1], p[2], p[3], p[4], p[5] or CAT_IMG[p[2]], p[6], p[7], ts)
                        for p in SEED_PRODUCTS
                    ],
                )
                set_meta(conn, "seeded", "1")
                print(f"[db] seeded reference catalog ({len(SEED_PRODUCTS)} products)")

            # keep previously-seeded databases in sync with the brand
            for slug, ar, fr, en in CATEGORY_NAME_UPDATES:
                conn.execute(
                    "UPDATE categories SET title_ar=?, title_fr=?, title_en=? WHERE slug=?",
                    (ar, fr, en, slug),
                )

            init_admin(conn)
            purge_expired_sessions(conn)

        with archive_db() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(ARCHIVE_SCHEMA)
            _ensure_column(conn, "old_products", "sizes", "TEXT")
            _ensure_column(conn, "old_products", "description", "TEXT")

        _migrate_old_products_to_archive()
    _migrate_legacy_uploads()


# ---------------------------------------------------------------------------
# admin account
# ---------------------------------------------------------------------------


def init_admin(conn):
    """Create the admin account once; upgrade legacy password hashes if any."""
    has_user = conn.execute("SELECT 1 FROM meta WHERE key='admin_user'").fetchone()
    stored_hash = get_meta(conn, "admin_pw_hash")
    if stored_hash and not stored_hash.startswith("pbkdf2$"):
        # legacy (SHA-256) hash from an older build -> re-seed with the
        # configured password using the current, slow hashing scheme.
        _reset_admin_password(conn, "legacy hash upgraded")
    if not has_user:
        if config.IS_PRODUCTION and not config.ADMIN_PASSWORD_FROM_ENV:
            raise SystemExit(
                "[auth] FIHI_ADMIN_PASSWORD must be set to create the admin account in production"
            )
        print(f"[auth] admin account created for user '{config.DEFAULT_ADMIN_USER}'")
        _reset_admin_password(conn, "initial account")
    if get_meta(conn, "mfa_enabled") is None:
        set_meta(conn, "mfa_enabled", "0")
    # FIHI_ADMIN_EMAIL is the source of truth: changing it on the platform
    # takes effect at the next start (the stored copy is only a fallback).
    if config.ADMIN_EMAIL_FROM_ENV or not get_meta(conn, "admin_email"):
        set_meta(conn, "admin_email", config.DEFAULT_ADMIN_EMAIL)


def get_reset_email(conn):
    """Address the reset link goes to: FIHI_ADMIN_EMAIL when set, else the stored one."""
    if config.ADMIN_EMAIL_FROM_ENV:
        return config.DEFAULT_ADMIN_EMAIL
    return get_meta(conn, "admin_email", "") or None


def create_reset_record(conn, email):
    """Issue a single-use reset token (30 min TTL) for a password reset."""
    token = secrets.token_hex(32)
    now_ts = int(time.time())
    conn.execute("DELETE FROM password_resets WHERE used=0")  # one pending reset at a time
    conn.execute(
        "INSERT INTO password_resets(token_hash,email,created,expires,used) VALUES(?,?,?,?,0)",
        (hash_token(token), email, now_ts, now_ts + config.RESET_TOKEN_TTL_MS // 1000),
    )
    return token


def consume_reset_token(conn, token):
    """Validate + consume a reset token; returns the account e-mail or None."""
    if not token:
        return None
    row = conn.execute(
        "SELECT id,email,expires FROM password_resets WHERE token_hash=? AND used=0",
        (hash_token(token),),
    ).fetchone()
    if not row:
        return None
    if int(time.time()) > row["expires"]:
        conn.execute("DELETE FROM password_resets WHERE id=?", (row["id"],))
        return None
    conn.execute("UPDATE password_resets SET used=1 WHERE id=?", (row["id"],))
    return row["email"]


def _reset_admin_password(conn, reason):
    pw = config.DEFAULT_ADMIN_PASS
    if len(pw) < config.MIN_PASSWORD_LEN:
        raise SystemExit(
            f"FIHI_ADMIN_PASSWORD must be at least {config.MIN_PASSWORD_LEN} characters"
        )
    salt = secrets.token_hex(8)
    set_meta(conn, "admin_user", config.DEFAULT_ADMIN_USER)
    set_meta(conn, "admin_pw_salt", salt)
    set_meta(conn, "admin_pw_hash", hash_password(pw, salt))
    print(f"[auth] admin credentials set ({reason})")


def set_admin_password(conn, password):
    """Store a new password (called by the password-reset flow)."""
    salt = secrets.token_hex(8)
    set_meta(conn, "admin_pw_salt", salt)
    set_meta(conn, "admin_pw_hash", hash_password(password, salt))


def verify_admin_password(conn, username, password):
    stored_user = get_meta(conn, "admin_user", "")
    stored_hash = get_meta(conn, "admin_pw_hash", "")
    salt = get_meta(conn, "admin_pw_salt", "")
    return username == stored_user and verify_password(password, salt, stored_hash)


def is_mfa_enabled(conn):
    return get_meta(conn, "mfa_enabled", "0") == "1"


# ---------------------------------------------------------------------------
# admin sessions (stored hashed, so deployments do not log the admin out)
# ---------------------------------------------------------------------------


def create_session(user, ip):
    token = secrets.token_urlsafe(32)
    now_ts = int(time.time())
    with _lock, live_db() as conn:
        purge_expired_sessions(conn)
        conn.execute(
            "INSERT INTO sessions(token_hash,user,ip,created,expires) VALUES(?,?,?,?,?)",
            (hash_token(token), user, ip, now_ts, now_ts + config.SESSION_TTL),
        )
    return token


def get_session(token):
    if not token:
        return None
    with live_db() as conn:
        row = conn.execute(
            "SELECT user,ip,created,expires FROM sessions WHERE token_hash=?",
            (hash_token(token),),
        ).fetchone()
    if not row or row["expires"] <= int(time.time()):
        return None
    return dict(row)


def delete_session(token):
    if not token:
        return
    with _lock, live_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (hash_token(token),))


def delete_all_sessions():
    with _lock, live_db() as conn:
        conn.execute("DELETE FROM sessions")


def purge_expired_sessions(conn):
    conn.execute("DELETE FROM sessions WHERE expires<=?", (int(time.time()),))


# ---------------------------------------------------------------------------
# archive migration (old builds kept old_products in the live database)
# ---------------------------------------------------------------------------


def _migrate_old_products_to_archive():
    with _lock, live_db() as live_conn:
        row = live_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='old_products'"
        ).fetchone()
        if not row:
            return
        old_products = live_conn.execute("SELECT * FROM old_products").fetchall()
        with archive_db() as archive_conn:
            for p in old_products:
                keys = p.keys()
                archive_conn.execute(
                    "INSERT OR IGNORE INTO old_products"
                    " (id, original_id, name, cat, min, max, img, ribbon, featured, custom,"
                    "  created, revoked_at, revoked_by, sizes)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        p["id"],
                        p["original_id"],
                        p["name"],
                        p["cat"],
                        p["min"],
                        p["max"],
                        p["img"],
                        p["ribbon"],
                        p["featured"],
                        p["custom"],
                        p["created"],
                        p["revoked_at"],
                        p["revoked_by"],
                        p["sizes"] if "sizes" in keys else None,
                    ),
                )
        live_conn.execute("DROP TABLE IF EXISTS old_products")
        if old_products:
            print(f"[db] migrated {len(old_products)} old products to the archive database")


# ---------------------------------------------------------------------------
# backups
# ---------------------------------------------------------------------------


def backup_zip():
    """Consistent snapshot of both databases + uploaded images, as zip bytes.

    Uses SQLite's online backup API, so it is safe while the shop is running.
    """
    buf = io.BytesIO()
    with (
        tempfile.TemporaryDirectory() as tmp,
        zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf,
    ):
        for path in (config.DB_FILE, config.ARCHIVE_DB_FILE):
            name = os.path.basename(path)
            copy = os.path.join(tmp, name)
            src, dst = _connect(path), sqlite3.connect(copy)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            zf.write(copy, name)
        if os.path.isdir(config.UPLOAD_DIR):
            for name in sorted(os.listdir(config.UPLOAD_DIR)):
                full = os.path.join(config.UPLOAD_DIR, name)
                if os.path.isfile(full) and not name.startswith("."):
                    zf.write(full, "uploads/" + name)
    return buf.getvalue()

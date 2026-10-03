"""SQLite persistence: schema, migrations, seeds and admin credential store."""

import os
import secrets
import sqlite3
import threading
import time

from . import config
from .security import hash_password, hash_token, verify_password

_lock = threading.RLock()
# Public name so other modules can serialize compound write transactions.
db_lock = _lock

# ---------------------------------------------------------------------------
# catalog seed (fihi-chifae home catalog)
# ---------------------------------------------------------------------------

SEED_CATEGORIES = [
    ("amlou",       "أملو",      "Amlou",       "Amlou",      config.P + "prod-amlou.svg"),
    ("miels",       "العسل",     "Miel",        "Honey",      config.P + "prod-miel.svg"),
    ("huiles",      "الزيوت",    "Huiles",      "Oils",       config.P + "cat-argan.svg"),
    ("cosmetiques", "عطور",      "Parfums",     "Perfumes",   config.P + "cat-promo.svg"),
    ("autres",      "منتوجات أخرى", "Autres produits", "Other products", config.P + "prod-pack.svg"),
    ("recettes",    "وصفات فيه شفاء", "Recettes", "Recipes",  config.P + "prod-coffret.svg"),
    ("packs",       "باقات فيه شفاء", "Packs",  "Packs",     config.P + "prod-pack.svg"),
    ("thes",        "الشاي",     "Thés",        "Teas",       config.P + "story.svg"),
]

# (id, name, cat, min, max, img, ribbon, featured)
SEED_PRODUCTS = [
    ("s-amlou-01", "أملو بالكاوكاو وزيت الزيتون والعسل",               "amlou", 95,  None, None, 0, 0),
    ("s-amlou-02", "أملو باللوز وزيت أركان والعسل الحر",                "amlou", 109, 239, None, 1, 1),
    ("s-amlou-03", "أملو باللوز وزيت الزيتون والعسل",                   "amlou", 99,  189, None, 0, 0),

    ("s-miels-01", "عسل السدر",             "miels", 350, None, config.P + "prod1.jpg", 0, 0),
    ("s-miels-02", "عسل الأكالبتوس الحر",   "miels", 350, None, config.P + "prod2.jpg", 0, 1),
    ("s-miels-03", "عسل الزعتر الحر",       "miels", 350, None, config.P + "prod3.jpg", 0, 0),
    ("s-miels-04", "عسل الخروب الحر",       "miels", 350, None, config.P + "prod4.jpg", 0, 0),
    ("s-miels-05", "عسل الزكوم الحر",       "miels", 350, None, config.P + "prod5.jpg", 0, 0),

    ("s-huiles-01", "زيت أركان للتجميل",   "huiles", 75,  None, None, 0, 0),
    ("s-huiles-02", "زيت أركان للأكل",     "huiles", 250, None, None, 0, 0),
    ("s-huiles-03", "زيت الزيتون",         "huiles", 140, None, None, 0, 0),
    ("s-huiles-04", "زيت الخروع",          "huiles", 80,  None, None, 0, 0),
    ("s-huiles-05", "زيت اللوز الحلو",     "huiles", 25,  None, None, 0, 0),
    ("s-huiles-06", "زيت اللوز المر",      "huiles", 25,  None, None, 0, 0),
    ("s-huiles-07", "زيت الأزير",          "huiles", 50,  None, None, 0, 0),
    ("s-huiles-08", "زيت السمسم",          "huiles", 35,  None, None, 0, 0),
    ("s-huiles-09", "زيت القنب الهندي",    "huiles", 65,  None, None, 0, 0),

    ("s-cosm-01", "صابونة الأركان",      "cosmetiques", 50, None, None, 0, 0),
    ("s-cosm-02", "كريم الشيا",          "cosmetiques", 50, None, None, 0, 0),
    ("s-cosm-03", "غاسول بالورد",        "cosmetiques", 60, None, None, 0, 0),
    ("s-cosm-04", "ماسك الطين الأخضر",   "cosmetiques", 35, None, None, 0, 0),
    ("s-cosm-05", "تونر ماء الورد",      "cosmetiques", 45, None, None, 0, 0),
    ("s-cosm-06", "سكراب الشفاه بالعسل", "cosmetiques", 28, 35,  None, 0, 0),

    ("s-autr-01", "سلو رويال",            "autres", 100, 150, None, 0, 0),
    ("s-autr-02", "الجيسينك بودرة",       "autres", None, None, None, 0, 0),
    ("s-autr-03", "العكبر الخام",         "autres", None, None, None, 0, 0),
    ("s-autr-04", "حبوب اللقاح",          "autres", None, None, None, 0, 0),
    ("s-autr-05", "خل التفاح",            "autres", 35,  None, None, 0, 0),
    ("s-autr-06", "الجيسينغ شرائح",       "autres", 140, None, None, 0, 0),
    ("s-autr-07", "العكبر البلدي بودرة",  "autres", 70,  None, None, 0, 0),
    ("s-autr-08", "ليبطون",               "autres", 35,  None, None, 0, 0),

    ("s-reci-01", "وجبة الطاقة",          "recettes", 220, 749, None, 1, 1),
    ("s-reci-02", "وصفة الجهاز الهضمي",   "recettes", 100, 360, None, 0, 0),
    ("s-reci-03", "الوصفة المقوية",       "recettes", 99,  580, None, 0, 0),
    ("s-reci-04", "الوصفة الملكية 👑",     "recettes", 99,  590, None, 1, 0),

    ("s-pack-01", "باقة رمضان",              "packs", 449, 689, None, 1, 1),
    ("s-pack-02", "باقة عيد الأضحى المبارك", "packs", 590, None, None, 0, 0),

    ("s-thes-01", "علي المقام",    "thes", None, None, None, 0, 0),
    ("s-thes-02", "كشمير",         "thes", None, None, None, 0, 0),
    ("s-thes-03", "جبل علي",       "thes", 80,  None, None, 0, 0),
    ("s-thes-04", "شاي الحاكم",    "thes", 105, None, None, 0, 0),
    ("s-thes-05", "المقام الذهبي", "thes", 105, None, None, 0, 0),
]

CAT_IMG = {c[0]: c[4] for c in SEED_CATEGORIES}

SCHEMA = """
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
    created TEXT
);
CREATE TABLE IF NOT EXISTS orders(
    id TEXT PRIMARY KEY,
    buyer TEXT,
    phone TEXT,
    created TEXT
);
CREATE TABLE IF NOT EXISTS order_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    product_name TEXT,
    cat TEXT,
    price REAL,
    qty INTEGER,
    created TEXT
);
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
    revoked_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_old_products_original ON old_products(original_id);
CREATE TABLE IF NOT EXISTS password_resets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL,
    email TEXT,
    created INTEGER NOT NULL,
    expires INTEGER NOT NULL,
    used INTEGER DEFAULT 0
);
"""

# Categories whose display name is brand-consistent and must stay in sync
# with previously-seeded databases.
CATEGORY_NAME_UPDATES = [
    ("recettes", "وصفات فيه شفاء", "Recettes", "Recipes"),
    ("packs", "باقات فيه شفاء", "Packs", "Packs"),
    ("cosmetiques", "عطور", "Parfums", "Perfumes"),
]


def db():
    conn = sqlite3.connect(config.DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# public alias used by the API layer
now = _now


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))


def unique_id(prefix):
    return "%s%d%s" % (prefix, int(time.time() * 1000), secrets.token_hex(3))


def init_db():
    """Create/migrate the schema and seed the reference catalog."""

    # One-time migration of the old database filename.
    legacy = os.path.join(config.BASE, "dhenbio.db")
    if not os.path.exists(config.DB_FILE) and os.path.exists(legacy):
        os.replace(legacy, config.DB_FILE)
        print("[db] migrated legacy database -> %s" % config.DB_FILE)

    with _lock:
        with db() as conn:
            conn.executescript(SCHEMA)

            seeded = get_meta(conn, "seeded")
            if not seeded:
                conn.executemany(
                    "INSERT OR REPLACE INTO categories(slug,title_ar,title_fr,title_en,img)"
                    " VALUES(?,?,?,?,?)",
                    SEED_CATEGORIES,
                )
                now = _now()
                conn.executemany(
                    "INSERT OR REPLACE INTO products"
                    " (id,name,cat,min,max,img,ribbon,featured,custom,created)"
                    " VALUES(?,?,?,?,?,?,?,?,0,?)",
                    [(p[0], p[1], p[2], p[3], p[4], p[5] or CAT_IMG[p[2]], p[6], p[7], now)
                     for p in SEED_PRODUCTS],
                )
                set_meta(conn, "seeded", "1")
                print("[db] seeded reference catalog (8 categories, %d products)" % len(SEED_PRODUCTS))

            # keep previously-seeded databases in sync with the brand
            for slug, ar, fr, en in CATEGORY_NAME_UPDATES:
                conn.execute(
                    "UPDATE categories SET title_ar=?, title_fr=?, title_en=? WHERE slug=?",
                    (ar, fr, en, slug),
                )

            init_admin(conn)


def init_admin(conn):
    """Create the admin account once; upgrade legacy password hashes if any."""
    has_user = conn.execute("SELECT 1 FROM meta WHERE key='admin_user'").fetchone()
    stored_hash = get_meta(conn, "admin_pw_hash")
    if stored_hash and not stored_hash.startswith("pbkdf2$"):
        # legacy (SHA-256) hash from an older build -> re-seed with the default
        # password using the current, slow hashing scheme.
        _reset_admin_password(conn, "hachage de mot de passe stabilisé")
    if not has_user:
        print("[auth] nouveau compte admin : %s / %s (variable FIHI_ADMIN_* pour changer)"
              % (config.DEFAULT_ADMIN_USER, config.DEFAULT_ADMIN_PASS))
        _reset_admin_password(conn, "compte initial")
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('mfa_enabled',?)",
                 (get_meta(conn, "mfa_enabled") or "0",))
    if not get_meta(conn, "admin_email"):
        set_meta(conn, "admin_email", config.DEFAULT_ADMIN_EMAIL)
        print("[auth] e-mail admin : %s (variable FIHI_ADMIN_EMAIL pour changer)"
              % config.DEFAULT_ADMIN_EMAIL)


def get_reset_email(conn):
    """Return the e-mail address a reset link can be sent to (or None)."""
    return get_meta(conn, "admin_email", "") or None


def create_reset_record(conn, email):
    """Issue a single-use reset token (30 min TTL) for a password reset."""
    token = secrets.token_hex(32)
    token_hash = hash_token(token)
    now_ts = int(time.time())
    conn.execute(
        "DELETE FROM password_resets WHERE used=0",  # one pending reset at a time
    )
    conn.execute(
        "INSERT INTO password_resets(token_hash,email,created,expires,used)"
        " VALUES(?,?,?,?,0)",
        (token_hash, email, now_ts, now_ts + config.RESET_TOKEN_TTL_MS // 1000),
    )
    return token


def consume_reset_token(conn, token):
    """Validate + consume a reset token; returns the account e-mail or None."""
    if not token:
        return None
    token_hash = hash_token(token)
    row = conn.execute(
        "SELECT id,email,expires FROM password_resets"
        " WHERE token_hash=? AND used=0",
        (token_hash,),
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
        raise SystemExit("FIHI_ADMIN_PASSWORD must be at least %d characters"
                         % config.MIN_PASSWORD_LEN)
    salt = secrets.token_hex(8)
    set_meta(conn, "admin_user", config.DEFAULT_ADMIN_USER)
    set_meta(conn, "admin_pw_salt", salt)
    set_meta(conn, "admin_pw_hash", hash_password(pw, salt))
    print("[auth] identifiants admin réinitialisés (%s)" % reason)


def set_admin_password(conn, password):
    """Store a new password (called by the password-reset flow)."""
    salt = secrets.token_hex(8)
    set_meta(conn, "admin_pw_salt", salt)
    set_meta(conn, "admin_pw_hash", hash_password(password, salt))


def verify_admin_password(conn, username, password):
    stored_user = get_meta(conn, "admin_user", "")
    stored_hash = get_meta(conn, "admin_pw_hash", "")
    salt = get_meta(conn, "admin_pw_salt", "")
    return (username == stored_user and
            verify_password(password, salt, stored_hash))


def is_mfa_enabled(conn):
    return get_meta(conn, "mfa_enabled", "0") == "1"
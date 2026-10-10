"""Central configuration for the fihi-chifae application.

Persistent data (both SQLite databases and uploaded images) lives in
``FIHI_DATA_DIR``. In production this directory is a mounted volume, so a new
release of the application never touches the data.
"""

import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV = os.environ.get("FIHI_ENV", "development").strip().lower()
IS_PRODUCTION = ENV == "production"

# ---------------------------------------------------------------------------
# Persistent data (mount a volume here in production, e.g. /data)
# ---------------------------------------------------------------------------
DATA_DIR = os.path.abspath(os.environ.get("FIHI_DATA_DIR", BASE))
# Live database - active data (products, categories, orders, sessions, ...)
DB_FILE = os.environ.get("FIHI_LIVE_DB", os.path.join(DATA_DIR, "fihi-chifae.db"))
# Archive database - deleted products and categories
ARCHIVE_DB_FILE = os.environ.get(
    "FIHI_ARCHIVE_DB", os.path.join(DATA_DIR, "fihi-chifae-archive.db")
)
# Uploaded product images. Locally they stay next to the code; with a data
# volume they move into it so they survive deployments too.
_LEGACY_UPLOAD_DIR = os.path.join(BASE, "assets", "uploads")
UPLOAD_DIR = os.environ.get(
    "FIHI_UPLOAD_DIR",
    _LEGACY_UPLOAD_DIR if DATA_DIR == BASE else os.path.join(DATA_DIR, "uploads"),
)
LEGACY_UPLOAD_DIR = _LEGACY_UPLOAD_DIR
# Public URL prefix of uploaded images (kept stable whatever UPLOAD_DIR is).
UPLOAD_URL_PREFIX = "assets/uploads/"

# Public asset path prefix used when storing relative image references.
P = "assets/"

SITE_NAME = "fihi-chifae"
# Insert the demo catalog into an empty database (local previews only).
SEED_DEMO = os.environ.get("FIHI_SEED_DEMO", "0") == "1"
TIMEZONE = os.environ.get("FIHI_TIMEZONE", "Africa/Casablanca")

# ---------------------------------------------------------------------------
# Admin credentials (used once, to create the account on a fresh database)
# ---------------------------------------------------------------------------
_DEFAULT_PASS = "admin2026"  # noqa: S105  # nosec B105 - dev only, refused in production
DEFAULT_ADMIN_USER = os.environ.get("FIHI_ADMIN_USER", "admin")
DEFAULT_ADMIN_PASS = os.environ.get("FIHI_ADMIN_PASSWORD", _DEFAULT_PASS)
ADMIN_PASSWORD_FROM_ENV = "FIHI_ADMIN_PASSWORD" in os.environ
# The password-reset link is always sent to this address (read on every start).
DEFAULT_ADMIN_EMAIL = os.environ.get("FIHI_ADMIN_EMAIL", "admin@fihi-chifae.com").strip()
ADMIN_EMAIL_FROM_ENV = bool(os.environ.get("FIHI_ADMIN_EMAIL", "").strip())

# ---------------------------------------------------------------------------
# SMTP configuration (used to deliver the password-reset e-mail).
# Leave unset -> reset links are printed to the server console instead.
# ---------------------------------------------------------------------------
SMTP_HOST = os.environ.get("FIHI_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("FIHI_SMTP_PORT", "587") or 587)
SMTP_USER = os.environ.get("FIHI_SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("FIHI_SMTP_PASSWORD", "")
SMTP_USE_TLS = os.environ.get("FIHI_SMTP_USE_TLS", "1") == "1"
EMAIL_FROM = os.environ.get("FIHI_EMAIL_FROM", "")


def _public_base_url():
    explicit = os.environ.get("FIHI_PUBLIC_BASE_URL", "").strip()
    if explicit:
        return explicit
    railway = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway:
        return "https://" + railway
    return ""


# Public base used to build the reset link. Never derived from the request's
# Host header in production (prevents reset-link poisoning).
PUBLIC_BASE_URL = _public_base_url()

# Password-reset token lifetime (single use).
RESET_TOKEN_TTL_MS = int(os.environ.get("FIHI_RESET_TOKEN_TTL_MIN", "30") or "30") * 60 * 1000

# ---------------------------------------------------------------------------
# Security / limits
# ---------------------------------------------------------------------------
SESSION_TTL = 8 * 3600  # admin session lifetime (seconds)
SESSION_COOKIE = "fc_session"
PASSWORD_ITERATIONS = 210_000  # PBKDF2 work factor
MIN_PASSWORD_LEN = 8

# Behind a reverse proxy (Railway, Fly, Render) the client IP comes from
# X-Forwarded-For; only trust it when told so.
TRUST_PROXY = os.environ.get("FIHI_TRUST_PROXY", "1" if IS_PRODUCTION else "0") == "1"

LOGIN_MAX_ATTEMPTS = 5  # failed logins allowed per window
LOGIN_WINDOW = 15 * 60  # rate-limit window (seconds)
# Public orders / newsletter sign-ups allowed per client IP per window.
# Overridable only so load tests (all users share one IP) are not throttled.
ORDER_MAX_PER_WINDOW = int(os.environ.get("FIHI_ORDER_RATE_LIMIT", "10") or 10)
ORDER_WINDOW = 10 * 60
NEWSLETTER_MAX_PER_WINDOW = int(os.environ.get("FIHI_NEWSLETTER_RATE_LIMIT", "5") or 5)
NEWSLETTER_WINDOW = 60 * 60

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # max image payload size
MAX_JSON_BODY = 16 * 1024 * 1024  # product adds carry a base64 image
MAX_SMALL_BODY = 64 * 1024  # login / orders / categories

MAX_NAME_LEN = 80
MAX_CATEGORY_NAME_LEN = 60
MAX_DESCRIPTION_LEN = 2000
MAX_FIELD_LEN = 200  # buyer name, address, city, location link
MAX_ORDER_ITEMS = 50
MAX_ITEM_QTY = 999

MAX_SIZES = 12  # max size variants per product
SIZE_UNITS = ("kg", "L")  # allowed measurement units
# Categories measured in litres by default (oils); everything else defaults to kg.
LIQUID_CATEGORIES = ("huiles",)

# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
DELIVERY_FEE = 40.0  # MAD
FREE_DELIVERY_THRESHOLD = 500.0  # MAD, items subtotal
# Delivery is always free in the shop's own city.
FREE_DELIVERY_CITY_LATIN = "BHALIL"
FREE_DELIVERY_CITY_AR = "البهاليل"

# WhatsApp number receiving the orders (international format, digits only).
WHATSAPP_NUMBER = "212681771457"

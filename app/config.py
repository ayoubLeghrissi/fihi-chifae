"""Central configuration for the fihi-chifae application."""

import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE, "fihi-chifae.db")
UPLOAD_DIR = os.path.join(BASE, "assets", "uploads")

# Public asset path prefix used when storing relative image references.
P = "assets/"

SITE_NAME = "fihi-chifae"

# ---------------------------------------------------------------------------
# Admin credentials (defaults, overridable through environment variables)
# ---------------------------------------------------------------------------
DEFAULT_ADMIN_USER = os.environ.get("FIHI_ADMIN_USER", "admin")
DEFAULT_ADMIN_PASS = os.environ.get("FIHI_ADMIN_PASSWORD", "admin2026")
DEFAULT_ADMIN_EMAIL = os.environ.get("FIHI_ADMIN_EMAIL", "admin@fihi-chifae.com")

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

# Public base used to build the reset link; falls back to the Host header.
PUBLIC_BASE_URL = os.environ.get("FIHI_PUBLIC_BASE_URL", "")

# Password-reset token lifetime (single use).
RESET_TOKEN_TTL_MS = int(os.environ.get("FIHI_RESET_TOKEN_TTL_MIN", "30") or "30") * 60 * 1000

# ---------------------------------------------------------------------------
# Security / limits
# ---------------------------------------------------------------------------
SESSION_TTL = 8 * 3600                       # admin session lifetime (seconds)
PASSWORD_ITERATIONS = 210_000                # PBKDF2 work factor
MIN_PASSWORD_LEN = 8

LOGIN_MAX_ATTEMPTS = 5                       # failed logins allowed per window
LOGIN_WINDOW = 15 * 60                       # rate-limit window (seconds)

MAX_UPLOAD_BYTES = 8 * 1024 * 1024           # max image payload size
MAX_JSON_BODY = 16 * 1024 * 1024             # product adds carry a base64 image
MAX_SMALL_BODY = 64 * 1024                   # login / orders / categories

MAX_NAME_LEN = 80
MAX_CATEGORY_NAME_LEN = 60
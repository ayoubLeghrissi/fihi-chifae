"""Security primitives: password hashing, session store, login throttling.

- Passwords are stored as PBKDF2-HMAC-SHA256: ``pbkdf2$<iterations>$<salt>$<hex>``.
- Admin sessions are opaque random tokens held in memory (server restart logs
  the user out, which is the expected behaviour for this application).
- Login throttling prevents brute-force attempts against the admin endpoint.
"""

import hashlib
import hmac
import secrets
import threading
import time

from .config import PASSWORD_ITERATIONS, LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW, SESSION_TTL

# ---------------------------------------------------------------------------
# password hashing
# ---------------------------------------------------------------------------

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return "pbkdf2$%d$%s$%s" % (PASSWORD_ITERATIONS, salt, digest.hex())


def verify_password(password, salt, stored_hash):
    if not stored_hash.startswith("pbkdf2$"):
        return False
    try:
        _, iterations_s, salt_s, expected = stored_hash.split("$", 3)
        iterations = int(iterations_s)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), (salt or salt_s).encode("utf-8"), iterations)
    return hmac.compare_digest(digest.hex(), expected)


def hash_token(token):
    """Store/compare reset & similar tokens by their SHA-256 digest."""
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# session store
# ---------------------------------------------------------------------------

class SessionStore:
    """In-memory admin sessions: token -> {exp, created, user, ip}."""

    def __init__(self, ttl=SESSION_TTL):
        self._ttl = ttl
        self._sessions = {}
        self._lock = threading.RLock()

    def _cleanup(self, now):
        stale = [t for t, s in self._sessions.items() if s["exp"] <= now]
        for t in stale:
            self._sessions.pop(t, None)

    def issue(self, user, ip):
        now = time.time()
        with self._lock:
            self._cleanup(now)
            token = secrets.token_hex(24)
            self._sessions[token] = {
                "exp": now + self._ttl,
                "created": int(now),
                "user": user,
                "ip": ip,
            }
            return {"token": token, "expires_in": self._ttl}

    def check(self, token):
        now = time.time()
        if not token:
            return None
        with self._lock:
            session = self._sessions.get(token)
            if not session or session["exp"] <= now:
                self._sessions.pop(token, None)
                return None
            return session

    def revoke(self, token):
        with self._lock:
            self._sessions.pop(token, None)

    def revoke_all(self):
        with self._lock:
            self._sessions.clear()


# ---------------------------------------------------------------------------
# login throttling (brute-force protection)
# ---------------------------------------------------------------------------

class LoginThrottle:
    def __init__(self, max_attempts=LOGIN_MAX_ATTEMPTS, window=LOGIN_WINDOW):
        self._max = max_attempts
        self._window = window
        self._fails = {}
        self._lock = threading.RLock()

    def record_failure(self, key):
        now = time.time()
        with self._lock:
            lst = [t for t in self._fails.get(key, []) if now - t < self._window]
            lst.append(now)
            self._fails[key] = lst

    def remaining(self, key):
        now = time.time()
        with self._lock:
            lst = [t for t in self._fails.get(key, []) if now - t < self._window]
            return max(0, self._max - len(lst))

    def blocked(self, key):
        """Return (is_blocked, retry_after_seconds)."""
        now = time.time()
        with self._lock:
            lst = [t for t in self._fails.get(key, []) if now - t < self._window]
            if len(lst) < self._max:
                return False, 0
            oldest = min(lst)
            return True, max(1, int(self._window - (now - oldest)))

    def success(self, key):
        with self._lock:
            self._fails.pop(key, None)


# ---------------------------------------------------------------------------
# response hardening headers (applied to every response by the handler)
# ---------------------------------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    ),
}
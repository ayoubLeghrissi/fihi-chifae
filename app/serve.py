"""HTTP layer: /api/v1 routes, whitelisted static files, admin page gating.

Design notes
------------
- Every JSON error uses the envelope ``{"error": {"code", "message"}}``.
- Admin authentication is an opaque session token in an HttpOnly,
  SameSite=Strict cookie (never readable by JavaScript). The admin pages are
  only served to an authenticated browser; others are redirected to the login.
- State-changing requests carrying a foreign ``Origin`` are refused (CSRF).
- Only an explicit set of files is served: the public pages and ``assets/``.
  Databases, source code and dotfiles are never reachable over HTTP.
- Login, order placement and newsletter sign-up are rate limited per client
  IP (taken from X-Forwarded-For when running behind the platform proxy).
"""

import argparse
import email.utils
import hashlib
import http.cookies
import json
import mimetypes
import os
import re
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import catalog, config, mailer, orders, sales
from . import db as database
from .catalog import StoreError
from .security import SECURITY_HEADERS, LoginThrottle

_login_throttle = LoginThrottle()
_reset_throttle = LoginThrottle(max_attempts=3, window=900)
_order_throttle = LoginThrottle(config.ORDER_MAX_PER_WINDOW, config.ORDER_WINDOW)
_newsletter_throttle = LoginThrottle(config.NEWSLETTER_MAX_PER_WINDOW, config.NEWSLETTER_WINDOW)

# Pre-encoded public catalog, rebuilt when the catalog version changes (or
# after CATALOG_CACHE_TTL seconds as a safety net).
CATALOG_CACHE_TTL = 60
_catalog_cache = {"version": None, "expires": 0.0, "body": b"", "etag": ""}

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
_ASSET_RE = re.compile(r"^/assets/([A-Za-z0-9_.-]+)$")
_UPLOAD_RE = re.compile(r"^/assets/uploads/([A-Za-z0-9_.-]+)$")

LOGIN_PAGE = "/admin-login.html"
PUBLIC_PAGES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/info.html": "info.html",
    LOGIN_PAGE: "admin-login.html",
    "/admin-reset.html": "admin-reset.html",
}
# Admin pages and the scripts that drive them: authenticated browsers only.
PROTECTED_FILES = {
    "/admin.html": "admin.html",
    "/admin-add.html": "admin-add.html",
    "/assets/admin.js": "assets/admin.js",
    "/assets/admin-add.js": "assets/admin-add.js",
}

mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("application/javascript", ".js")

# ---------------------------------------------------------------------------
# route table: (HTTP method, path regex, handler attribute)
# ---------------------------------------------------------------------------

_ROUTES = [
    ("GET", r"/api/v1/ping", "_h_ping"),
    ("GET", r"/api/v1/catalog", "_h_catalog"),
    ("POST", r"/api/v1/orders", "_h_create_order"),
    ("POST", r"/api/v1/newsletter", "_h_newsletter"),
    ("GET", r"/api/v1/admin/session", "_h_admin_session"),
    ("POST", r"/api/v1/admin/session", "_h_admin_login"),
    ("DELETE", r"/api/v1/admin/session", "_h_admin_logout"),
    ("POST", r"/api/v1/admin/verify-mfa", "_h_admin_mfa"),
    ("POST", r"/api/v1/admin/reset/request", "_h_reset_request"),
    ("POST", r"/api/v1/admin/reset/confirm", "_h_reset_confirm"),
    ("GET", r"/api/v1/sales/summary", "_h_sales_summary"),
    ("GET", r"/api/v1/sales/export", "_h_sales_export"),
    ("GET", r"/api/v1/orders", "_h_list_orders"),
    ("POST", r"/api/v1/admin/orders", "_h_admin_create_order"),
    ("POST", r"/api/v1/orders/([^/]+)/confirm", "_h_confirm_order"),
    ("POST", r"/api/v1/orders/([^/]+)/reject", "_h_reject_order"),
    ("POST", r"/api/v1/categories", "_h_create_category"),
    ("DELETE", r"/api/v1/categories/([^/]+)", "_h_delete_category"),
    ("POST", r"/api/v1/products", "_h_add_product"),
    ("PUT", r"/api/v1/products/([^/]+)", "_h_update_product"),
    ("POST", r"/api/v1/products/([^/]+)/update", "_h_update_product"),
    ("DELETE", r"/api/v1/products/([^/]+)", "_h_delete_product"),
    ("POST", r"/api/v1/products/([^/]+)/revoke", "_h_delete_product"),
    ("GET", r"/api/v1/archive", "_h_archive"),
    ("GET", r"/api/v1/admin/backup", "_h_backup"),
    ("POST", r"/api/v1/archive/products/([^/]+)/restore", "_h_restore_product"),
]
_ROUTES = [(m, re.compile("^" + p + "$"), f) for m, p, f in _ROUTES]


def _route(method, path):
    for meth, rx, func in _ROUTES:
        if meth == method:
            match = rx.match(path)
            if match:
                return func, match
    return None, None


def _path_known(path):
    return any(rx.match(path) for _, rx, _ in _ROUTES)


class AppHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # no keep-alive: a fresh instance per request
    server_version = "fihi-chifae"
    sys_version = ""

    @property
    def _path(self):
        return urllib.parse.urlparse(self.path).path

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {self._client_ip()} -- {fmt % args}\n")

    # ------------------------------------------------------------- helpers
    def _client_ip(self):
        if config.TRUST_PROXY:
            fwd = self.headers.get("X-Forwarded-For", "")
            if fwd:
                # the right-most entry is the one appended by the platform proxy
                return fwd.split(",")[-1].strip()
        return self.client_address[0]

    def _is_https(self):
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https" or config.IS_PRODUCTION

    def end_headers(self):
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        if self._is_https():
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        super().end_headers()

    def _json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            if isinstance(v, list):
                for item in v:
                    self.send_header(k, item)
            else:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, status, code, message, headers=None, **extra):
        payload = {"error": {"code": code, "message": message}}
        payload.update(extra)
        self._json(status, payload, headers=headers)

    def _body_json(self, limit):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return {}
        if length > limit:
            self._error(413, "payload_too_large", "حجم الطلب كبير جداً")
            return None
        content_type = (self.headers.get("Content-Type") or "").lower()
        if "json" not in content_type:
            self._error(415, "unsupported_media_type", "Content-Type يجب أن يكون application/json")
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._error(400, "invalid_json", "بيانات JSON غير صالحة")
            return None
        if not isinstance(data, dict):
            self._error(400, "invalid_json", "يجب أن تكون البيانات كائن JSON")
            return None
        return data

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _rate_limited(self, throttle, key, message):
        blocked, retry_after = throttle.blocked(key)
        if blocked:
            self._error(
                429,
                "rate_limited",
                message,
                headers={"Retry-After": str(retry_after)},
                retry_after=retry_after,
            )
        return blocked

    # ------------------------------------------------------------ sessions
    def _session_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return ""
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return ""
        morsel = jar.get(config.SESSION_COOKIE)
        return morsel.value if morsel else ""

    def _session(self):
        return database.get_session(self._session_token())

    def _cookie(self, token, max_age):
        parts = [
            f"{config.SESSION_COOKIE}={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Strict",
            f"Max-Age={max_age}",
        ]
        if self._is_https():
            parts.append("Secure")
        return "; ".join(parts)

    def _require_admin(self):
        session = self._session()
        if session:
            self._current_user = session["user"]
            return session["user"]
        self._error(401, "unauthorized", "المصادقة مطلوبة", auth_required=True)
        return None

    def _origin_ok(self):
        """Refuse cross-site state-changing requests (defence in depth vs CSRF)."""
        origin = self.headers.get("Origin")
        if not origin or origin == "null":
            return origin is None
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").lower()
        return urllib.parse.urlparse(origin).netloc.lower() == host

    # ------------------------------------------------------------- dispatch
    def _dispatch(self, method):
        path = self._path
        func, match = _route(method, path)
        if func:
            if method != "GET" and not self._origin_ok():
                self._error(403, "bad_origin", "طلب غير مسموح")
                return
            self._run(func, match)
            return
        if path.startswith("/api/"):
            if path.startswith("/api/v1/"):
                if _path_known(path):
                    self._error(405, "method_not_allowed", "الطريقة غير مسموحة لهذا المورد")
                else:
                    self._error(404, "not_found", "المسار غير موجود")
            else:
                self._error(410, "endpoint_deprecated", "هذه الواجهة قديمة: استخدم /api/v1/*")
            return
        if method in ("GET", "HEAD"):
            self._serve_static()
            return
        self._error(405, "method_not_allowed", "الطريقة غير مسموحة")

    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("HEAD" if not self._path.startswith("/api/") else "GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _run(self, func, match):
        try:
            getattr(self, func)(match)
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # never leak internals to the client
            sys.stderr.write(f"[error] {self.command} {self._path}: {exc!r}\n")
            try:
                self._error(500, "internal_error", "خطأ داخلي في الخادم")
            except Exception:  # noqa: S110  # nosec B110 - best-effort reply
                pass

    # --------------------------------------------------------------- static
    def _serve_static(self):
        path = self._path
        if path in PROTECTED_FILES:
            if not self._session():
                if path.endswith(".html"):
                    self._redirect(LOGIN_PAGE + "?next=" + urllib.parse.quote(path))
                else:
                    self._error(401, "unauthorized", "المصادقة مطلوبة", auth_required=True)
                return
            self._send_file(os.path.join(config.BASE, PROTECTED_FILES[path]), private=True)
            return
        if path == LOGIN_PAGE and self._session():
            self._redirect("/admin.html")
            return
        if path in PUBLIC_PAGES:
            self._send_file(os.path.join(config.BASE, PUBLIC_PAGES[path]))
            return
        if path == "/favicon.ico":
            self._send_file(os.path.join(config.BASE, "assets", "logo.jpg"))
            return
        m = _UPLOAD_RE.match(path)
        if m:
            self._send_file(os.path.join(config.UPLOAD_DIR, m.group(1)), immutable=True)
            return
        m = _ASSET_RE.match(path)
        if m and not m.group(1).startswith("."):
            self._send_file(os.path.join(config.BASE, "assets", m.group(1)))
            return
        self._not_found()

    def _not_found(self):
        body = "404 - الصفحة غير موجودة".encode()
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_file(self, full, private=False, immutable=False):
        try:
            st = os.stat(full)
        except OSError:
            self._not_found()
            return
        if not os.path.isfile(full):
            self._not_found()
            return
        last_modified = email.utils.formatdate(st.st_mtime, usegmt=True)
        ims = self.headers.get("If-Modified-Since")
        if ims and not private:
            try:
                if int(st.st_mtime) <= email.utils.parsedate_to_datetime(ims).timestamp():
                    self.send_response(304)
                    self.send_header("Last-Modified", last_modified)
                    self.end_headers()
                    return
            except (TypeError, ValueError, IndexError, OverflowError):
                pass
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        if private:
            cache = "no-store"
        elif immutable:
            cache = "public, max-age=31536000, immutable"
        else:
            cache = "no-cache"  # revalidate (cheap 304) so new releases show immediately
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(st.st_size))
        self.send_header("Last-Modified", last_modified)
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(full, "rb") as fh:
            while chunk := fh.read(64 * 1024):
                self.wfile.write(chunk)

    # ------------------------------------------------------------- public
    def _h_ping(self, match):
        self._json(200, {"status": "ok", "service": config.SITE_NAME, "time": time.time()})

    def _h_catalog(self, match):
        cache = _catalog_cache
        version = catalog.catalog_version()
        if cache["version"] != version or time.time() > cache["expires"]:
            data = catalog.grouped_catalog()
            data["settings"] = {
                "whatsapp": config.WHATSAPP_NUMBER,
                "delivery_fee": config.DELIVERY_FEE,
                "free_delivery_threshold": config.FREE_DELIVERY_THRESHOLD,
                "free_delivery_cities": [
                    config.FREE_DELIVERY_CITY_LATIN,
                    config.FREE_DELIVERY_CITY_AR,
                ],
            }
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            cache.update(
                version=version,
                expires=time.time() + CATALOG_CACHE_TTL,
                body=body,
                etag='"' + hashlib.sha256(body).hexdigest()[:32] + '"',
            )
        body, etag = cache["body"], cache["etag"]
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")  # always revalidate (cheap 304)
        self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _h_create_order(self, match):
        ip = self._client_ip()
        if self._rate_limited(_order_throttle, ip, "عدد كبير من الطلبات، يرجى المحاولة لاحقاً"):
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        source = "chatbot" if payload.get("source") == "chatbot" else "online"
        result = orders.create_order(payload, manual=False, source=source)
        _order_throttle.record_failure(ip)  # counts placed orders, not failures
        self._json(201, result)

    def _h_newsletter(self, match):
        ip = self._client_ip()
        if self._rate_limited(_newsletter_throttle, ip, "يرجى المحاولة لاحقاً"):
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        email_addr = str(payload.get("email", "")).strip().lower()
        if not _EMAIL_RE.match(email_addr):
            self._error(400, "invalid_email", "البريد الإلكتروني غير صالح")
            return
        lang = str(payload.get("lang", ""))[:2]
        _newsletter_throttle.record_failure(ip)
        with database.db_lock, database.live_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO newsletter(email,lang,created) VALUES(?,?,?)",
                (email_addr, lang, database.now()),
            )
        self._json(200, {"ok": True})

    # -------------------------------------------------------------- auth
    def _h_admin_session(self, match):
        session = self._session()
        if not session:
            self._error(401, "unauthorized", "المصادقة مطلوبة", auth_required=True)
            return
        self._json(
            200,
            {
                "ok": True,
                "user": session["user"],
                "expires_in": max(0, int(session["expires"] - time.time())),
            },
        )

    def _h_admin_login(self, match):
        ip = self._client_ip()
        blocked, retry_after = _login_throttle.blocked(ip)
        if blocked:
            self._error(
                429,
                "rate_limited",
                "محاولات كثيرة، يرجى المحاولة لاحقاً",
                headers={"Retry-After": str(retry_after)},
                retry_after=retry_after,
            )
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "") or "")
        if not username or not password:
            self._error(400, "missing_credentials", "اسم المستخدم وكلمة المرور مطلوبان")
            return
        with database.live_db() as conn:
            ok = database.verify_admin_password(conn, username, password)
            mfa = database.is_mfa_enabled(conn)
        if not ok:
            _login_throttle.record_failure(ip)
            self._error(
                401,
                "invalid_credentials",
                "بيانات الدخول غير صحيحة",
                remaining_attempts=_login_throttle.remaining(ip),
            )
            return
        _login_throttle.success(ip)
        if mfa:
            self._json(200, {"mfa_required": True, "message": "أدخل رمز التحقق"})
            return
        token = database.create_session(username, ip)
        self._json(
            200,
            {"ok": True, "expires_in": config.SESSION_TTL},
            headers={"Set-Cookie": self._cookie(token, config.SESSION_TTL)},
        )

    def _h_admin_logout(self, match):
        database.delete_session(self._session_token())
        self._json(200, {"ok": True}, headers={"Set-Cookie": self._cookie("", 0)})

    def _h_admin_mfa(self, match):
        self._error(501, "mfa_not_available", "التحقق بخطوتين غير مفعل بعد", mfa_coming=True)

    def _reset_link(self, token):
        base = config.PUBLIC_BASE_URL
        if not base:
            if config.IS_PRODUCTION:
                return None  # never trust the Host header in production
            base = "http://" + (self.headers.get("Host") or "127.0.0.1")
        return base.rstrip("/") + "/admin-reset.html?token=" + token

    def _h_reset_request(self, match):
        key = "reset:" + self._client_ip()
        if self._rate_limited(_reset_throttle, key, "طلبات كثيرة، يرجى المحاولة لاحقاً"):
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        _reset_throttle.record_failure(key)
        email_addr = str(payload.get("email", "")).strip().lower()
        with database.db_lock, database.live_db() as conn:
            account_email = database.get_reset_email(conn)
            if email_addr and account_email and email_addr == account_email.lower():
                token = database.create_reset_record(conn, email_addr)
                link = self._reset_link(token)
                if link:
                    mailer.send_password_reset(email_addr, link)
                else:
                    sys.stderr.write("[auth] FIHI_PUBLIC_BASE_URL not set: reset e-mail not sent\n")
        # identical response whether or not the e-mail exists (no enumeration)
        self._json(200, {"ok": True, "message": "إذا كان البريد مسجلاً، سيتم إرسال رابط الاستعادة"})

    def _h_reset_confirm(self, match):
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        token = str(payload.get("token", "")).strip()
        new_password = str(payload.get("password", "") or "")
        if len(new_password) < config.MIN_PASSWORD_LEN:
            self._error(
                400,
                "weak_password",
                f"كلمة المرور يجب أن تتكون من {config.MIN_PASSWORD_LEN} أحرف على الأقل",
            )
            return
        with database.db_lock, database.live_db() as conn:
            if not database.consume_reset_token(conn, token):
                self._error(
                    400, "invalid_token", "هذا الرابط غير صالح أو منتهي الصلاحية: أعد الطلب"
                )
                return
            database.set_admin_password(conn, new_password)
        database.delete_all_sessions()
        self._json(200, {"ok": True, "message": "تم تحديث كلمة المرور، يرجى تسجيل الدخول"})

    # ------------------------------------------------------------- admin
    def _h_sales_summary(self, match):
        if self._require_admin() is None:
            return
        self._json(200, sales.sales_summary())

    def _h_sales_export(self, match):
        if self._require_admin() is None:
            return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ym = (query.get("month") or [""])[0] or None
        if ym and not _MONTH_RE.match(ym):
            self._error(400, "invalid_month", "شهر غير صالح (YYYY-MM)")
            return
        buf, fname = sales.export_month(ym)
        data = buf.getvalue()
        self.send_response(200)
        self.send_header(
            "Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _h_list_orders(self, match):
        if self._require_admin() is None:
            return
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        date_from = (query.get("from") or [""])[0] or None
        date_to = (query.get("to") or [""])[0] or None
        self._json(200, {"orders": orders.list_orders(date_from, date_to)})

    def _h_admin_create_order(self, match):
        if self._require_admin() is None:
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        self._json(201, orders.create_order(payload, manual=True))

    def _h_confirm_order(self, match):
        if self._require_admin() is None:
            return
        self._json(200, orders.confirm_order(match.group(1)))

    def _h_reject_order(self, match):
        if self._require_admin() is None:
            return
        self._json(200, orders.reject_order(match.group(1)))

    def _h_create_category(self, match):
        if self._require_admin() is None:
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        self._json(201, {"category": catalog.create_category(str(payload.get("name", "")))})

    def _h_delete_category(self, match):
        user = self._require_admin()
        if user is None:
            return
        self._json(200, catalog.delete_category(match.group(1), user))

    def _h_add_product(self, match):
        if self._require_admin() is None:
            return
        payload = self._body_json(config.MAX_JSON_BODY)
        if payload is None:
            return
        raw_price = payload.get("price")
        price = None
        if raw_price not in (None, ""):
            try:
                price = round(float(raw_price), 2)
            except (TypeError, ValueError):
                self._error(400, "invalid_price", "السعر غير صالح")
                return
        result = catalog.add_product(
            str(payload.get("name", "")),
            str(payload.get("cat", "")),
            price,
            str(payload.get("img", "") or ""),
            sizes=payload.get("sizes"),
            description=str(payload.get("description", "") or ""),
        )
        self._json(201, result)

    def _h_update_product(self, match):
        if self._require_admin() is None:
            return
        payload = self._body_json(config.MAX_JSON_BODY)
        if payload is None:
            return

        def opt(key):
            if key not in payload or payload[key] is None:
                return None
            return str(payload[key])

        result = catalog.update_product(
            match.group(1),
            name=opt("name"),
            cat=opt("cat"),
            price=payload.get("price") if "price" in payload else None,
            img_source=opt("img") or None,
            sizes=payload.get("sizes") if "sizes" in payload else None,
            description=opt("description"),
        )
        self._json(200, result)

    def _h_delete_product(self, match):
        user = self._require_admin()
        if user is None:
            return
        pid = match.group(1)
        old_id = catalog.archive_product(pid, user)
        self._json(200, {"ok": True, "deleted": pid, "archived": True, "old_id": old_id})

    def _h_archive(self, match):
        if self._require_admin() is None:
            return
        self._json(200, catalog.list_archive())

    def _h_backup(self, match):
        if self._require_admin() is None:
            return
        data = database.backup_zip()
        stamp = database.now()[:16].replace(":", "").replace("T", "-")
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        fname = f"fihi-chifae-backup-{stamp}.zip"
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _h_restore_product(self, match):
        if self._require_admin() is None:
            return
        self._json(200, catalog.restore_product(match.group(1)))


# Backward-compatible name.
QuietHandler = AppHandler


class ShopServer(ThreadingHTTPServer):
    """Threaded server sized for traffic bursts.

    The stdlib default listen backlog is 5: under a burst, extra connections
    are refused and clients retry after 1 s, 3 s, 7 s... (huge tail latency).
    """

    request_queue_size = 1024
    daemon_threads = True


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="fihi-chifae web shop + SQLite API")
    parser.add_argument(
        "--host",
        default="0.0.0.0",  # noqa: S104  # nosec B104 - container binding
        help="bind address (0.0.0.0 = reachable from the LAN)",
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--open", action="store_true", help="open a browser tab automatically")
    args = parser.parse_args(argv)

    database.init_db()
    server = ShopServer((args.host, args.port), AppHandler)

    url = f"http://{args.host}:{args.port}/"
    print("=" * 64)
    print(f"  {config.SITE_NAME} ({config.ENV}) is running at: {url}")
    print(f"  Admin dashboard:   {url}admin.html")
    print(f"  Data directory:    {config.DATA_DIR}")
    print(f"  Live database:     {config.DB_FILE}")
    print(f"  Archive database:  {config.ARCHIVE_DB_FILE}")
    print(f"  Uploads:           {config.UPLOAD_DIR}")
    print("  Press Ctrl+C to stop.")
    print("=" * 64, flush=True)

    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()

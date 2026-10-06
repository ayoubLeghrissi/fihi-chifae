"""HTTP layer: standardized /api/v1 REST-like routes + static file serving.

Design notes
------------
- Every JSON response uses the envelope ``{"error": {"code", "message"}}`` on
  failures and plain data payloads on success.
- Admin-only routes require the ``X-Token`` header issued by the login route.
- Login is throttled per client IP; the password check is constant-time.
- Security headers (CSP, X-Frame-Options, nosniff, ...) are applied to every
  response in ``end_headers``.
- Legacy ``/api/*`` routes answer ``410 Gone`` so stale clients fail loudly
  instead of silently breaking.
"""

import argparse
import functools
import json
import re
import sys
import time
import urllib.parse
import webbrowser

try:
    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
except ImportError:  # Python < 3.7
    from http.server import HTTPServer as ThreadingHTTPServer
    from http.server import SimpleHTTPRequestHandler

from . import config
from . import db as database
from . import catalog
from . import mailer
from . import sales
from .catalog import (
    StoreError,
    add_product,
    create_category,
    delete_product,
    grouped_catalog,
    revoke_product,
    update_product,
)
from .security import SECURITY_HEADERS, LoginThrottle, SessionStore

_session_store = SessionStore()
_login_throttle = LoginThrottle()
_reset_throttle = LoginThrottle(max_attempts=3, window=900)

_STATIC_EXTS = (".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".html", ".webp", ".ico", ".xlsx")

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

# ---------------------------------------------------------------------------
# route table: (HTTP method, path regex, handler attribute)
# ---------------------------------------------------------------------------

_ROUTES = [
    ("GET", re.compile(r"^/api/v1/ping$"), "_h_ping"),
    ("GET", re.compile(r"^/api/v1/catalog$"), "_h_catalog"),
    ("GET", re.compile(r"^/api/v1/admin/session$"), "_h_admin_session"),
    ("POST", re.compile(r"^/api/v1/admin/session$"), "_h_admin_login"),
    ("DELETE", re.compile(r"^/api/v1/admin/session$"), "_h_admin_logout"),
    ("POST", re.compile(r"^/api/v1/admin/verify-mfa$"), "_h_admin_mfa"),
    ("POST", re.compile(r"^/api/v1/admin/reset/request$"), "_h_reset_request"),
    ("POST", re.compile(r"^/api/v1/admin/reset/confirm$"), "_h_reset_confirm"),
    ("GET", re.compile(r"^/api/v1/sales/summary$"), "_h_sales_summary"),
    ("GET", re.compile(r"^/api/v1/sales/export$"), "_h_sales_export"),
    ("POST", re.compile(r"^/api/v1/categories$"), "_h_create_category"),
    ("DELETE", re.compile(r"^/api/v1/categories/([^/]+)$"), "_h_delete_category"),
    ("POST", re.compile(r"^/api/v1/products$"), "_h_add_product"),
    ("PUT", re.compile(r"^/api/v1/products/([^/]+)$"), "_h_update_product"),
    ("POST", re.compile(r"^/api/v1/products/([^/]+)$"), "_h_update_product"),
    ("POST", re.compile(r"^/api/v1/products/([^/]+)/update$"), "_h_update_product"),
    ("DELETE", re.compile(r"^/api/v1/products/([^/]+)$"), "_h_delete_product"),
    ("POST", re.compile(r"^/api/v1/products/([^/]+)/revoke$"), "_h_revoke_product"),
    ("POST", re.compile(r"^/api/v1/orders$"), "_h_create_order"),
]


def _route(method, path):
    for meth, rx, func in _ROUTES:
        if meth != method:
            continue
        match = rx.match(path)
        if match:
            return func, match
    return None, None


class QuietHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # no keep-alive: a fresh instance per request

    @property
    def _path(self):
        return urllib.parse.urlparse(self.path).path

    def log_message(self, fmt, *args):
        msg = fmt % args
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} -- {msg}\n")

    # ------------------------------------------------------------------ base
    def end_headers(self):
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        path = self._path
        if path.endswith(_STATIC_EXTS):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
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
            self._error(413, "payload_too_large", "requête trop lourde")
            return None
        content_type = (self.headers.get("Content-Type") or "").lower()
        if "json" not in content_type:
            self._error(415, "unsupported_media_type", "Content-Type doit être application/json")
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._error(400, "invalid_json", "corps JSON invalide")
            return None
        if not isinstance(data, dict):
            self._error(400, "invalid_json", "le corps doit être un objet JSON")
            return None
        return data

    def _current_token(self):
        return (self.headers.get("X-Token") or "").strip()

    def _require_admin(self):
        session = _session_store.check(self._current_token())
        if session:
            self._current_user = session["user"]
            return session["user"]
        self._error(401, "unauthorized", "authentification requise", auth_required=True)
        return None

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        path = self._path
        func, match = _route("GET", path)
        if func:
            self._run(func, match)
            return
        if path.startswith("/api/"):
            for meth in ("POST", "DELETE", "PUT"):
                other, _ = _route(meth, path)
                if other:
                    self._error(
                        405, "method_not_allowed", "méthode non autorisée pour cette ressource"
                    )
                    return
            if path.startswith("/api/v1/"):
                self._error(404, "not_found", "route inconnue")
            else:
                self._error(
                    410, "endpoint_deprecated", "cette API est obsolète : utilisez /api/v1/*"
                )
            return
        super().do_GET()

    # ------------------------------------------------------------------ POST
    def do_POST(self):
        func, match = _route("POST", self._path)
        if func:
            self._run(func, match)
            return
        if self._path.startswith("/api/"):
            # support method override via ?_method=PUT or POST to PUT fallback
            for meth in ("PUT", "DELETE"):
                other, _ = _route(meth, self._path)
                if other:
                    self._error(
                        405, "method_not_allowed", "méthode non autorisée pour cette ressource"
                    )
                    return
            self._error(404, "not_found", "route inconnue")
            return
        self._error(404, "not_found", "route inconnue")

    # ----------------------------------------------------------------- DELETE
    def do_DELETE(self):
        func, match = _route("DELETE", self._path)
        if func:
            self._run(func, match)
            return
        if self._path.startswith("/api/"):
            self._error(404, "not_found", "route inconnue")
            return
        self._error(404, "not_found", "route inconnue")

    # -------------------------------------------------------------------- PUT
    def do_PUT(self):
        func, match = _route("PUT", self._path)
        if func:
            self._run(func, match)
            return
        if self._path.startswith("/api/"):
            self._error(404, "not_found", "route inconnue")
            return
        self._error(404, "not_found", "route inconnue")

    def _run(self, func, match):
        try:
            getattr(self, func)(match)
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
        except BrokenPipeError:
            pass
        except Exception as exc:  # never leak internals to the client
            sys.stderr.write(f"[error] {exc!r}\n")
            try:
                self._error(500, "internal_error", "erreur interne du serveur")
            except Exception:  # noqa: S110 - response already best-effort
                pass

    # ------------------------------------------------------------- handlers
    def _h_ping(self, match):
        self._json(200, {"status": "ok", "service": config.SITE_NAME, "time": time.time()})

    def _h_catalog(self, match):
        self._json(200, grouped_catalog())

    def _h_admin_session(self, match):
        user = self._require_admin()
        if user is None:
            return
        session = _session_store.check(self._current_token())
        self._json(
            200, {"ok": True, "user": user, "expires_in": max(0, int(session["exp"] - time.time()))}
        )

    def _h_admin_login(self, match):
        ip = self.client_address[0]
        blocked, retry_after = _login_throttle.blocked(ip)
        if blocked:
            self._error(
                429,
                "rate_limited",
                "trop de tentatives, réessayez plus tard",
                headers={"Retry-After": str(retry_after)},
                retry_after=retry_after,
                auth_required=True,
            )
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "") or "")
        if not username or not password:
            self._error(400, "missing_credentials", "identifiant et mot de passe requis")
            return

        with database.db() as conn:
            ok = database.verify_admin_password(conn, username, password)
            mfa = database.is_mfa_enabled(conn)
        if not ok:
            _login_throttle.record_failure(ip)
            self._error(
                401,
                "invalid_credentials",
                "identifiants incorrects",
                auth_required=True,
                remaining_attempts=_login_throttle.remaining(ip),
            )
            return
        _login_throttle.success(ip)
        if mfa:
            self._json(
                200, {"mfa_required": True, "message": "saisissez votre code de vérification"}
            )
            return
        session = _session_store.issue(username, ip)
        self._json(
            200,
            {"token": session["token"], "expires_in": session["expires_in"], "mfa_enabled": False},
        )

    def _h_admin_logout(self, match):
        _session_store.revoke(self._current_token())
        self._json(200, {"ok": True})

    def _h_admin_mfa(self, match):
        self._error(
            501,
            "mfa_not_available",
            "l'authentification à deux facteurs n'est pas encore activée",
            mfa_coming=True,
        )

    def _reset_link(self, token):
        base = config.PUBLIC_BASE_URL or ("http://" + (self.headers.get("Host") or "127.0.0.1"))
        return base.rstrip("/") + "/admin-reset.html?token=" + token

    def _h_reset_request(self, match):
        ip = self.client_address[0]
        key = "reset:" + ip
        blocked, retry_after = _reset_throttle.blocked(key)
        if blocked:
            self._error(
                429,
                "rate_limited",
                "trop de demandes, réessayez plus tard",
                headers={"Retry-After": str(retry_after)},
                retry_after=retry_after,
            )
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        _reset_throttle.record_failure(key)
        email = str(payload.get("email", "")).strip().lower()
        with database.db_lock:
            with database.db() as conn:
                account_email = database.get_reset_email(conn)
                if email and account_email and email == account_email.lower():
                    token = database.create_reset_record(conn, email)
                    mailer.send_password_reset(email, self._reset_link(token))
        # identical response whether or not the e-mail exists (no enumeration)
        self._json(
            200,
            {"ok": True, "message": "si cet e-mail est enregistré, un lien vient d'être envoyé"},
        )

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
                f"le mot de passe doit faire au moins {config.MIN_PASSWORD_LEN} caractères",
            )
            return
        with database.db_lock:
            with database.db() as conn:
                email = database.consume_reset_token(conn, token)
                if not email:
                    self._error(
                        400,
                        "invalid_token",
                        "ce lien est invalide ou a expiré : refaites une demande",
                    )
                    return
                database.set_admin_password(conn, new_password)
        _session_store.revoke_all()
        self._json(
            200, {"ok": True, "message": "mot de passe mis à jour, veuillez vous reconnecter"}
        )

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
            self._error(400, "invalid_month", "mois invalide, format attendu YYYY-MM")
            return
        buf, fname = sales.export_month(ym)
        data = buf.getvalue()
        self.send_response(200)
        self.send_header(
            "Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _h_create_category(self, match):
        if self._require_admin() is None:
            return
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        name = str(payload.get("name", ""))
        try:
            category = create_category(name)
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
            return
        self._json(201, {"category": category})

    def _h_delete_category(self, match):
        if self._require_admin() is None:
            return
        slug = match.group(1)
        try:
            result = catalog.delete_category(slug)
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
            return
        self._json(200, result)

    def _h_add_product(self, match):
        if self._require_admin() is None:
            return
        payload = self._body_json(config.MAX_JSON_BODY)
        if payload is None:
            return
        name = str(payload.get("name", ""))
        cat = str(payload.get("cat", ""))
        img = str(payload.get("img", "") or "")
        raw_price = payload.get("price")
        price = None
        if raw_price not in (None, ""):
            try:
                price = round(float(raw_price), 2)
            except (TypeError, ValueError):
                self._error(400, "invalid_price", "prix invalide")
                return
        sizes = payload.get("sizes") if "sizes" in payload else None
        try:
            result = add_product(name, cat, price, img, sizes=sizes)
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
            return
        self._json(201, result)

    def _h_update_product(self, match):
        if self._require_admin() is None:
            return
        pid = match.group(1)
        payload = self._body_json(config.MAX_JSON_BODY)
        if payload is None:
            return
        # champs optionnels – None = inchangé
        name = payload.get("name") if "name" in payload else None
        cat = payload.get("cat") if "cat" in payload else None
        img = payload.get("img") if "img" in payload else None
        raw_price = payload.get("price") if "price" in payload else None
        price = raw_price
        sizes = payload.get("sizes") if "sizes" in payload else None
        # normaliser types pour la couche domaine
        if name is not None:
            name = str(name)
        if cat is not None:
            cat = str(cat)
        if img is not None:
            img = str(img or "")
            if img == "":
                img = None  # "" signifie inchangé côté front pour éviter écrasement
        try:
            result = update_product(
                pid, name=name, cat=cat, price=price, img_source=img, sizes=sizes
            )
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
            return
        self._json(200, result)

    def _h_delete_product(self, match):
        if self._require_admin() is None:
            return
        pid = match.group(1)
        try:
            delete_product(pid)
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
            return
        self._json(200, {"ok": True, "deleted": pid})

    def _h_revoke_product(self, match):
        user = self._require_admin()
        if user is None:
            return
        pid = match.group(1)
        try:
            rev_id = revoke_product(pid, user)
        except StoreError as exc:
            self._error(exc.status, exc.code, exc.message, **exc.extra)
            return
        self._json(200, {"ok": True, "revoked": pid, "old_id": rev_id})

    def _h_create_order(self, match):
        payload = self._body_json(config.MAX_SMALL_BODY)
        if payload is None:
            return
        buyer = str(payload.get("buyer", "")).strip()
        phone = str(payload.get("phone", "")).strip()
        items = payload.get("items")
        if not buyer:
            self._error(400, "missing_buyer", "le nom de l'acheteur est obligatoire")
            return
        if not isinstance(items, list) or not items:
            self._error(400, "empty_cart", "le panier est vide")
            return
        clean = []
        for it in items:
            name = str(it.get("name", "")).strip()
            try:
                price = round(float(it.get("price", 0)), 2)
                qty = int(it.get("qty", 0))
            except (TypeError, ValueError):
                self._error(400, "invalid_item", "données de l'article invalides")
                return
            if not name or qty < 1 or price < 0:
                self._error(400, "invalid_item", "données de l'article invalides")
                return
            clean.append(
                {
                    "name": name,
                    "price": price,
                    "qty": qty,
                    "cat": str(it.get("cat", "")) or "autres",
                    "size": str(it.get("size", "") or ""),
                }
            )

        oid = database.unique_id("o")
        now = database.now()
        with database.db_lock:
            with database.db() as conn:
                conn.execute(
                    "INSERT INTO orders(id,buyer,phone,created) VALUES(?,?,?,?)",
                    (oid, buyer, phone, now),
                )
                conn.executemany(
                    "INSERT INTO order_items(order_id,product_name,cat,price,qty,created,size)"
                    " VALUES(?,?,?,?,?,?,?)",
                    [
                        (oid, it["name"], it["cat"], it["price"], it["qty"], now, it["size"])
                        for it in clean
                    ],
                )
        total = round(sum(it["price"] * it["qty"] for it in clean), 2)
        self._json(201, {"ok": True, "order_id": oid, "total": total})


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="fihi-chifae static server + SQLite API")
    parser.add_argument(
        "--host",
        default="0.0.0.0",  # noqa: S104 - intentional LAN binding
        help="bind address (0.0.0.0 = reachable from the LAN)",
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="open a browser tab automatically")
    args = parser.parse_args(argv)

    database.init_db()

    handler = functools.partial(QuietHandler, directory=config.BASE)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    url = f"http://{args.host}:{args.port}/"
    print("=" * 64)
    print(f"  {config.SITE_NAME} is running at: {url}")
    print(f"  Admin dashboard:       {url}admin.html")
    print(f"  Add product page:      {url}admin-add.html")
    print(f"  Password reset page:   {url}admin-reset.html (email/SMTP)")
    print(f"  API base:              {url}api/v1/")
    print(f"  SQLite database:       {config.DB_FILE}")
    print(f"  Excel export:          {url}api/v1/sales/export?month=YYYY-MM (admin)")
    print("  Press Ctrl+C to stop.")
    print("=" * 64)

    if args.open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()

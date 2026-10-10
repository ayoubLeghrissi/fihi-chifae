"""fihi-chifae (فيه شفاء) - application entry point.

Run locally:
    python server.py [--port 8000] [--open]

The application lives in the ``app`` package (config, db, security, catalog,
orders, sales, serve). This file only boots it.

API overview (all under /api/v1/; "admin" = HttpOnly session cookie required):
    GET    /ping                              health check
    GET    /catalog                           public catalog, best sellers, delivery settings
    POST   /orders                            place an order (public, priced server-side)
    POST   /newsletter                        newsletter sign-up (public)
    GET    /admin/session                     current session
    POST   /admin/session                     login (sets the session cookie)
    DELETE /admin/session                     logout
    POST   /admin/reset/request|confirm       password reset by e-mail
    GET    /sales/summary                     KPIs + charts (admin)
    GET    /sales/export?month=YYYY-MM        Excel report of confirmed sales (admin)
    GET    /orders?from=YYYY-MM-DD&to=...     orders with their lines (admin)
    POST   /admin/orders                      manual order, confirmed at once (admin)
    POST   /orders/{id}/confirm|reject        confirm / reject-and-delete (admin)
    POST   /categories, DELETE /categories/{id}        (admin; delete = archive)
    POST   /products, PUT|DELETE /products/{id}        (admin; delete = archive)
    GET    /archive, POST /archive/products/{id}/restore   (admin)
    GET    /admin/backup                      zip of both databases + images (admin)
"""

from app.serve import main

if __name__ == "__main__":
    main()

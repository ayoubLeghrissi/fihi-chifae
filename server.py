"""fihi-chifae (فيه شفاء) - application entry point.

Run:
    python server.py [--port 8000] [--open]

The application logic lives in the ``app`` package (db, security, catalog,
sales, serve). This file only boots it so ``python server.py`` keeps working.

API overview (all under /api/v1/):
    GET  /ping                       -> health check
    GET  /catalog                    -> public grouped catalog + best sellers
    POST /orders                     -> place an order (public)
    POST /admin/session              -> login (username/password)
    GET  /admin/session              -> validate the current session
    DELETE /admin/session            -> logout
    POST /admin/verify-mfa           -> reserved for MFA (501 until enabled)
    POST /categories                 -> create a category (admin)
    POST /products                   -> add a product (admin)
    DELETE /products/{id}            -> permanently delete a custom product
    POST /products/{id}/revoke       -> move a product to old_products (admin)
    GET  /sales/summary              -> KPIs + charts data (admin)
    GET  /sales/export?month=YYYY-MM -> Excel report (admin)
"""

from app.serve import main

if __name__ == "__main__":
    main()
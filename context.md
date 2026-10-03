# Project context (compact)
Root: C:\Users\eurek\Downloads\fihi-chifae\mielyoussef-clone
API v1 under /api/v1 with JSON error envelope; legacy /api/* -> 410; method -> 405; crash -> 500.
Auth: PBKDF2-HMAC-SHA256 210k, sessions in-memory (TTL 8h), login throttled 5/15m -> 429+Retry-After.
Password reset: public, rate-limited, enumeration-safe; 30min single-use token, SMTP or console fallback; meta admin_email (default admin@fihi-chifae.com, FIHI_ADMIN_EMAIL); all sessions revoked after reset; min 8 chars.
Catalog: cosmetiques renamed to عطور (seed + migration), featured, categories; old_products holds revoked (keep files); custom delete allowed, protected -> 403; images data: or assets/ with magic-byte sniff png/jpg/webp/gif/svg, <=8MB.
Orders: POST /api/v1/orders persists to DB (sales/export/dashboard). Checkout also opens WhatsApp to +212682884917 with name + product*qty + totals.
Security: security headers, CSP (tune as needed), image validation, no secrets in code.
LAN: bind 0.0.0.0, current LAN IP 192.168.0.111; firewall allows TCP 8000 (profile any) where elevated; AP/Client Isolation may block phone.
Server: server.py (thin), app/ package. python -m compileall passes.

LAN_best_ip=192.168.0.111

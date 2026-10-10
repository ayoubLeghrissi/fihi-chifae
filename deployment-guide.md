# fihi-chifae — deployment guide (Railway)

## The one rule: data lives on a volume, code lives in the image

| What | Where | Survives a new release? |
|---|---|---|
| Application code, pages, CSS/JS | Docker image (rebuilt on every deploy) | replaced on purpose |
| `fihi-chifae.db` (live: catalog, orders, sessions, newsletter) | volume mounted at `/data` | **yes** |
| `fihi-chifae-archive.db` (deleted products & categories) | volume `/data` | **yes** |
| Uploaded product images | volume `/data/uploads` | **yes** |

The app reads `FIHI_DATA_DIR=/data` (already set in the Dockerfile). Databases are
created and migrated automatically at start-up; a release never resets them.

### Why not a separate "database service"?
SQLite is a file, not a server: a second Railway service cannot share it with the
app, and it would bill a second always-on container. A **volume attached to the
app service** is the cheapest option (billed only per GB stored — this shop
needs well under 1 GB) and it is exactly what keeps the data across releases.

## One-time setup on Railway

1. **New project → Deploy from GitHub repo** (or empty service + CLI). Railway
   detects `railway.json` and builds the `Dockerfile`.
2. **Attach a volume**: service → *Settings* → *Volumes* → *Add volume*,
   mount path **`/data`**. (CLI: `railway volume add --mount-path /data`.)
3. **Variables** (service → *Variables*):

   | Variable | Value |
   |---|---|
   | `FIHI_ADMIN_PASSWORD` | a long passphrase (required the first time) |
   | `FIHI_ADMIN_USER` | e.g. `admin` |
   | `FIHI_ADMIN_EMAIL` | your e-mail (password reset) |
   | `FIHI_SMTP_*`, `FIHI_EMAIL_FROM` | optional, to e-mail reset links |

   `PORT` and `RAILWAY_PUBLIC_DOMAIN` are provided by Railway; the reset link uses
   the public domain automatically. Keep **1 replica** (SQLite = one writer).
4. **Networking** → *Generate domain*.
5. To deploy **only when you decide**, turn off *Settings → Deploy → automatic
   deploys from GitHub* and use the workflow below (or `railway up`).

> The container starts as root only to `chown` the mounted volume, then drops to
> an unprivileged user — no `RAILWAY_RUN_UID` setting needed.

## Releasing a new version (manual button)

GitHub → **Actions → "CI/CD" → Run workflow → target: `railway`**.
The job runs lint + tests + security checks, then `railway up`. It needs:

* secret **`RAILWAY_TOKEN`** — Railway project → *Settings → Tokens* (project token);
* variable **`RAILWAY_SERVICE`** — the service name;
* optional variable **`PUBLIC_URL`** (e.g. `https://xxx.up.railway.app`) for a post-deploy smoke test.

Other targets in the same dropdown (only if you ever need them): `fly`
(`FLY_API_TOKEN`, volume `fihi_data` from `fly.toml`) and `render`
(`RENDER_DEPLOY_HOOK`, disk from `render.yaml`). Nothing deploys automatically.

From a terminal instead: `railway login && railway link && make deploy`.

## Performance (load) test

Runs automatically after every push to `main`, or on demand: **Actions → CI/CD → Run
workflow** (target `none`, tick *Run the performance test*, choose users / duration /
vCPU / RAM). The production image runs in a fresh container per stage (default 1 vCPU,
512 MB, demo catalog) while Locust simulates shoppers browsing, loading the catalog and
ordering, plus one admin on the dashboard. Resource usage is sampled every second.

Results: the run page shows a summary table; the **perf-report** artifact contains
`report.html` (charts: throughput, response times, CPU, RAM per stage) plus the raw Locust
reports and CSVs. Locally: `make perf` (needs Docker).

## Backups (free)

Dashboard → **نسخة احتياطية** downloads a zip with a consistent copy of both
databases and all images (`GET /api/v1/admin/backup`). Do it before big changes
and keep a copy off-platform. Restore = stop the service, put the files back into
`/data` (e.g. `railway ssh`), start again.

## Local development

```bash
pip install -r requirements-dev.txt
python server.py --open          # data in the project folder, admin / admin2026
make test                        # tests may use the real local DBs but must delete
                                 # everything they create (enforced in tests/conftest.py)
make docker-build && make docker-run   # production-like, data in volume "fihi-data"
```

## Security summary

* Admin pages and admin API require an HttpOnly + Secure + SameSite=Strict session cookie;
  unauthenticated visits to `/admin.html` are redirected to `/admin-login.html`.
* Only public pages and `assets/` are served — databases, code and dotfiles return 404.
* Prices and delivery fees are always computed on the server.
* Login, order and newsletter endpoints are rate limited per client IP.
* Strict CSP (no inline scripts), HSTS, no-sniff, frame-deny headers.
* Production refuses to start without `FIHI_ADMIN_PASSWORD` on a fresh database.

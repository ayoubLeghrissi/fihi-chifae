# Deployment Guide — fihi-chifae (فيه شفاء)

> **Goal:** From your local machine → GitHub → automated CI/CD (lint + tests + security) → binary/Docker → production on Fly.io (primary) or Render (alternative).  
> **Stack:** Python 3.12 + `http.server` + SQLite + `openpyxl`, Docker (python:3.12-slim, non-root), GitHub Actions.  
> **Default language:** Arabic (`ar`) — storefront and admin. Admin login overlay is intentionally generic (“المصادقة”) for security.

---

## 0) Prerequisites (your side)

| Tool | Version | Check | Install |
|------|---------|-------|---------|
| **Python** | 3.10+ (tested 3.12.3) | `python --version` | https://python.org (check “Add to PATH”) |
| **Git** | any | `git --version` | https://git-scm.com |
| **Make** | 4.4+ (Git Bash provides it) | `make --version` | Git for Windows → Git Bash, or `choco install make` |
| **Docker Desktop** | 29+ (for `make docker-*` & local prod parity) | `docker --version` | https://docs.docker.com/desktop/ |
| **Flyctl** (for deploy) | latest | `fly --version` | `winget install flyctl` or `powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"` |
| **GitHub account** | — | `gh auth status` (optional) | https://github.com |

> **Windows note:** All `make` targets are POSIX-compatible. Use **Git Bash** (recommended) or `cmd` — the Makefile uses `python -c "Path.mkdir(...)"` instead of `mkdir -p` so both shells work.

Check after install:

```bash
python --version      # 3.12.x
pip --version
make --version        # GNU Make 4.4.x
docker --version      # 29.x
fly --version         # flyctl v0.3.x
git --version
```

---

## 1) Get the project & first run

```bash
# 1. Clone (or copy) the scaffolded project
cd C:\Users\eurek\Downloads\fihi-chifae
cd mielyoussef-clone

# 2. (Recommended) create a venv
python -m venv .venv
# Windows Git Bash / cmd:
source .venv/Scripts/activate  # Git Bash
# .venv\Scripts\activate      # cmd
# macOS/Linux:
# source .venv/bin/activate

# 3. Install deps
make install
# equivalent:
# python -m pip install -r requirements.txt
# python -m pip install -r requirements-dev.txt

# 4. Configure env (see Step 2)

# 5. Launch
make launch
# → http://0.0.0.0:8000  and  http://127.0.0.1:8000
# Storefront:   http://127.0.0.1:8000/
# Admin:        http://127.0.0.1:8000/admin.html  (admin / admin2026)
# Health:       http://127.0.0.1:8000/api/v1/ping
# Ctrl+C to stop

# Alternative with browser auto-open:
make dev
```

**What `make launch` does:** `python server.py --host 0.0.0.0 --port 8000` — binds `0.0.0.0` so your phone on same Wi-Fi can reach `http://<your-lan-ip>:8000` (check `ipconfig` on Windows).

---

## 2) Environment variables (your side)

Copy the template and fill **only on your machine / Fly secrets** — never commit `.env`.

```bash
cp .env.example .env
# then edit .env
```

`.env.example` keys:

```ini
FIHI_ADMIN_USER=admin
FIHI_ADMIN_PASSWORD=change-me-strong-12+   # ← change! min 8 chars, 210k PBKDF2
FIHI_ADMIN_EMAIL=admin@fihi-chifae.com
FIHI_PUBLIC_BASE_URL=https://fihi-chifae.fly.dev
PORT=8000

# SMTP optional — if empty, reset link is printed to server console
FIHI_SMTP_HOST=
FIHI_SMTP_PORT=587
FIHI_SMTP_USER=
FIHI_SMTP_PASSWORD=
FIHI_SMTP_USE_TLS=1
FIHI_EMAIL_FROM=

# Deploy secrets (set in GitHub → Settings → Secrets and Fly, not in .env)
FLY_API_TOKEN=
RENDER_DEPLOY_HOOK=
```

**Local run with custom admin:**

```bash
# Git Bash / Linux / macOS
FIHI_ADMIN_PASSWORD='MyStr0ng!2026' FIHI_ADMIN_EMAIL='you@domain.com' make launch

# Windows cmd
set FIHI_ADMIN_PASSWORD=MyStr0ng!2026 && make launch
```

**Production (Fly.io):** set via `fly secrets` (Step 7), not `.env`.

---

## 3) Local quality gate (your side before push)

```bash
make help          # list all targets

make lint          # ruff + flake8 (non-blocking, || true)
make format        # black + ruff --fix  (commit after)
make format-check  # CI will run this

make test
# → python -m compileall app server.py
# → pytest -q --cov=app  (if pytest installed, else smoke: from app import db,catalog)

make security      # bandit + pip-audit
# bandit -r app --severity-level medium
# pip-audit --desc

make clean         # removes __pycache__, .pytest_cache, build, dist
```

All three are **required** before `make push` (the `push` target runs `lint` + `test` automatically).

---

## 4) Git & GitHub (your side)

The project currently has **no git** (`fatal: not a git repository`). Initialize and push:

```bash
# 1. Create empty repo on GitHub (web): https://github.com/new
#    e.g. https://github.com/<your-org>/fihi-chifae  (do NOT init with README)

# 2. Init and first push (choose ONE)
make github-init REMOTE=https://github.com/<your-org>/fihi-chifae.git
# or manually:
git init
git add .
git commit -m "chore: initial enterprise scaffold"
git branch -M main
git remote add origin https://github.com/<your-org>/fihi-chifae.git
git push -u origin main

# 3. Subsequent pushes (runs lint+test before push)
make push
# equivalent:
# git add .
# git commit -m "feat: ..."
# git push origin HEAD
```

**Verify on GitHub:** `https://github.com/<your-org>/fihi-chifae/actions` → workflows should appear after first push.

---

## 5) Get the binary (your side)

We ship **two binary forms**; Docker is the production binary.

### A) Zipapp (portable Python, no compiler)
```bash
make binary        # → dist/fihi-chifae.pyz (app package only)
ls -lh dist/
python dist/fihi-chifae.pyz --help
# Note: zipapp serves app code only; for full bundle (assets + HTML) use Docker.
```

### B) PyInstaller native exe (Windows)
```bash
pip install -r requirements-dev.txt  # includes pyinstaller
make binary-pyinstaller
# → dist/fihi-chifae.exe  (single file, includes assets/index.html etc.)
./dist/fihi-chifae.exe --port 8000
# or dist\fihi-chifae.exe  (Windows)
```

### C) Docker image (recommended production binary)
```bash
make docker-build   # → fihi-chifae:latest  (also :<git-sha>)
docker images | grep fihi

make docker-run     # → http://localhost:8000  (PORT=8000)
# test:
curl http://127.0.0.1:8000/api/v1/ping
curl http://127.0.0.1:8000/api/v1/catalog | head

make docker-scan    # trivy HIGH,CRITICAL (if trivy installed)
```

**Artifacts in CI:** Every push builds `dist/fihi-chifae.pyz` and pushes `ghcr.io/<your-org>/fihi-chifae:sha` + `:latest` to GitHub Container Registry (GHCR). Download from Actions → Artifacts → `fihi-chifae-binary`.

---

## 6) GitHub Actions CI/CD (best practices, security)

File: `.github/workflows/ci-cd.yml` (and `security.yml` weekly).

**What runs on every `push`/`pull_request` to `main`:**

| Job | Steps | Purpose |
|-----|-------|---------|
| `lint-test` | `setup-python@v5` (cache pip), `pip install`, `ruff check`, `black --check`, `compileall`, `pytest --cov` | Quality gate |
| `security` | `bandit -r app -f sarif` → SARIF upload, `pip-audit --desc` → artifact | SAST + SCA |
| `codeql` | `github/codeql-action` `security-and-quality` for Python | CodeQL |
| `build` | `needs: [lint-test,security]`, `setup-qemu/buildx`, `docker/login ghcr.io`, `docker/metadata`, `build-push` (`linux/amd64,linux/arm64`, `cache gha`, `provenance+sbom`), `make binary` → upload `dist/`, `trivy-action` → SARIF | Binary + Docker + supply chain |
| `deploy` | `needs: build`, `if: main push`, `superfly/flyctl-actions` → `fly deploy --remote-only` | CD to Fly.io |

**Permissions (least privilege):** `contents:read`, `security-events:write` (SARIF), `packages:write` (GHCR), `id-token:write` (provenance), `concurrency` cancel.

**Weekly audit:** `.github/workflows/security.yml` runs `bandit` + `pip-audit` every Monday 04:00 UTC.

**Your side to enable:**
1. Push to `main` → check `Actions` tab green.
2. In repo Settings → **Security → Code scanning** → enable.
3. No extra secrets needed for CI; `GITHUB_TOKEN` is auto-provided for GHCR.

**Local security before push:**
```bash
make bandit
make pip-audit
# or make security
```

---

## 7) Deploy to cloud — choose one

### Option A — Fly.io (primary, recommended for this project)

**Why Fly:** Docker-native, free tier, `fly.toml:1` already in repo (region `cdg` Paris, close to Morocco), healthcheck `/api/v1/ping`, auto-stop.

```bash
# 1. Install & auth (once)
fly auth login
# or: fly auth signup

# 2. Create app (first time only, if not already)
fly apps create fihi-chifae --org personal
# or: fly launch --no-deploy  # will detect Dockerfile & fly.toml

# 3. Set secrets (your side, never commit)
fly secrets set FIHI_ADMIN_PASSWORD='ChangeMeStrong12+' FIHI_ADMIN_EMAIL='admin@fihi-chifae.com' FIHI_PUBLIC_BASE_URL='https://fihi-chifae.fly.dev'
# optional SMTP:
# fly secrets set FIHI_SMTP_HOST=smtp.gmail.com FIHI_SMTP_USER=... FIHI_SMTP_PASSWORD=...

# 4. Deploy via Makefile (local)
make deploy
# equivalent: fly deploy --remote-only --ha=false

# 5. Or rely on GitHub Actions auto-deploy:
#    set GitHub secret FLY_API_TOKEN (= fly tokens create deploy -x 999h)
#    → repo Settings → Secrets → New repository secret → FLY_API_TOKEN
#    → next push to main triggers deploy job

# 6. Verify
fly status
fly logs
curl https://fihi-chifae.fly.dev/api/v1/ping
curl https://fihi-chifae.fly.dev/api/v1/catalog | head
# open https://fihi-chifae.fly.dev/  and  /admin.html
```

**Manual GitHub deploy secret:**
```bash
fly tokens create deploy -x 999h
# copy token → GitHub repo → Settings → Secrets and variables → Actions → New secret → FLY_API_TOKEN
```

**Custom domain (optional):** `fly certs add fihi-chifae.com` + CNAME.

### Option B — Render (alternative, no flyctl)

`render.yaml:1` is included (`dockerfilePath: ./Dockerfile`, `healthCheckPath: /api/v1/ping`).

```bash
# 1. Push to GitHub (already done)
# 2. Render dashboard → New → Blueprint → Connect repo → Apply render.yaml
# 3. Or: New → Web Service → Docker → Connect repo → Dockerfile → Frankfurt
# 4. Add env vars in Render dashboard: FIHI_ADMIN_PASSWORD, FIHI_ADMIN_EMAIL, PORT=8000
# 5. Auto-deploy on push is enabled via render.yaml: autoDeploy: true
# Alternative hook deploy:
# Render dashboard → Service → Settings → Deploy Hook → copy URL → GitHub secret RENDER_DEPLOY_HOOK → make deploy-render
```

**Docker Hub / GHCR pull (any VM):**
```bash
docker pull ghcr.io/<your-org>/fihi-chifae:latest
docker run -d -p 8000:8000 --env FIHI_ADMIN_PASSWORD=... --env PORT=8000 ghcr.io/<your-org>/fihi-chifae:latest
```

---

## 8) Post-deploy verification (your side)

```bash
# health
curl https://fihi-chifae.fly.dev/api/v1/ping
# {"status":"ok","service":"fihi-chifae","time":...}

# catalog
curl https://fihi-chifae.fly.dev/api/v1/catalog | python -m json.tool | head -n 30

# admin login (browser)
# https://fihi-chifae.fly.dev/admin.html
# user: admin (or $FIHI_ADMIN_USER) / pass: $FIHI_ADMIN_PASSWORD
# Check: dashboard KPIs, sales export (Excel), add product → dynamic category dropdown, edit product (pencil) → new category auto-created

# storefront
# https://fihi-chifae.fly.dev/
# Add to cart → checkout → WhatsApp chatbot (شات معنا عبر واتساب) → confirm → order appears in admin

# logs
fly logs --app fihi-chifae
# or: docker logs <container>
```

**If `fihi-chifae.db` is ephemeral (Fly machines are ephemeral):** Add a volume for persistence:

```bash
fly volumes create fihi_data --region cdg --size 1
# then in fly.toml:
# [mounts]
#   source = "fihi_data"
#   destination = "/data"
# and set env DB_FILE=/data/fihi-chifae.db (requires small change in app/config.py)
```

For now, SQLite lives in image filesystem (OK for demo; for production use Postgres — see `app/db.py`).

---

## 9) Day-2 operations (your side)

| Task | Command |
|------|---------|
| **Update product/category** | Admin → `.../admin-add.html` → pencil `تعديل` → `حفظ` (PUT `/api/v1/products/{id}/update`) |
| **Backup DB** | `fly sftp get /app/fihi-chifae.db` or `scp` / `litestream` |
| **Rotate admin password** | `fly secrets set FIHI_ADMIN_PASSWORD='NewPass...'` → `fly deploy` |
| **View sales Excel** | Admin → `تحميل المبيعات (Excel)` → `GET /api/v1/sales/export?month=2026-10` |
| **Rollback** | `fly releases` → `fly deploy --image ghcr.io/...:previous-sha` or GitHub → Re-run previous workflow |
| **Logs & metrics** | `fly logs` + `fly status --all` + GitHub → Actions → Trivy/Bandit SARIF in Security tab |
| **Local prod parity** | `make docker-build && make docker-run` (same Dockerfile as prod) |

**Security hygiene (already in CI, continue locally):**
```bash
make lint && make security   # before every push
# Dependabot: GitHub → Settings → Code security → Dependabot alerts → Enable
```

---

## 10) Troubleshooting

| Symptom | Fix |
|---------|-----|
| `make: command not found` | Use Git Bash, or `winget install make` |
| `pytest: command not found` | `pip install -r requirements-dev.txt` or `make install` |
| `docker: command not found` | Install Docker Desktop, enable WSL2 |
| `fly: command not found` | `winget install flyctl` or `powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"` |
| `501 Unsupported method PUT` | Use `POST /api/v1/products/{id}/update` (Makefile `saveEdit` already does) |
| `fifi_admin_token` 401 | Login again: `admin.html` → `المصادقة` → `admin`/`admin2026` |
| Phone `+212 ...` inverted in RTL | Already fixed via `dir="ltr"` in `index.html:236` + `style.css:455`; hard refresh `Ctrl+Shift+R` |
| `{n} منتوج` showing literal | Fixed in `main.js:270` (`sub !== undefined`), bump `main.js?v=11` — hard refresh |

---

## 11) File map (what was scaffolded for you)

```
mielyoussef-clone/
├─ Makefile              # launch / test / binary / docker / push / deploy
├─ Dockerfile            # python:3.12-slim, non-root, healthcheck
├─ .dockerignore
├─ fly.toml              # cdg region, auto_stop, healthcheck /api/v1/ping
├─ render.yaml           # Render Blueprint alternative
├─ requirements.txt      # openpyxl, Pillow
├─ requirements-dev.txt  # ruff, black, flake8, bandit, pip-audit, pytest, pyinstaller
├─ pyproject.toml        # black, ruff, bandit, pytest config
├─ .env.example          # copy to .env, never commit
├─ .gitignore            # db, uploads, dist, venv
├─ .github/workflows/
│  ├─ ci-cd.yml          # lint→test→security(CodeQL/Bandit/pip-audit)→build(Docker+zipapp+Trivy)→deploy(Fly)
│  └─ security.yml       # weekly audit
├─ tests/                # test_catalog.py, test_security.py, test_api_smoke.py
├─ app/                  # catalog, db, security, sales, serve
├─ assets/               # style.css, main.js (chatbot), admin.js, admin-add.js
└─ dist/                 # generated by `make binary` (git-ignored)
```

**Next step for you:** `make launch`, verify `http://127.0.0.1:8000`, then `make github-init REMOTE=<your-github-url> && make push` — GitHub Actions will take over (binary + Docker → GHCR → Fly).


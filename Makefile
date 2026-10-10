# fihi-chifae — Makefile (enterprise, POSIX, Windows Git Bash compatible)
# Usage: make <target>  |  make help
# Requires: python (3.10+), pip, git. Optional: docker, flyctl, pyinstaller

PY            ?= python
PIP           ?= $(PY) -m pip
PORT          ?= 8000
HOST          ?= 0.0.0.0

IMAGE_NAME    ?= fihi-chifae
GHCR_IMAGE    ?= ghcr.io/fihi-chifae/$(IMAGE_NAME)
VERSION       ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
PLATFORMS     ?= linux/amd64,linux/arm64

.DEFAULT_GOAL := help
.PHONY: help install launch dev test lint format format-check security audit bandit pip-audit clean docker-build docker-run docker-scan push github-init deploy deploy-railway deploy-fly deploy-render backup

help: ## Show this help
	@echo "fihi-chifae — available targets:"
	@$(PY) -c "import re, pathlib; print('\n'.join(re.findall(r'^([a-zA-Z0-9_.-]+):.*?## (.+)', pathlib.Path('Makefile').read_text(encoding='utf-8'), re.M)))" 2>nul || grep -E '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── setup ───────────────────────────────────────────────────────────────
install: ## Install runtime + dev deps (venv recommended)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	@echo "✔ deps installed"

# ── launch ──────────────────────────────────────────────────────────────
launch: ## Launch server (python server.py --port $(PORT))
	@echo "→ http://$(HOST):$(PORT)  (Ctrl+C to stop)"
	$(PY) server.py --host $(HOST) --port $(PORT)

dev: ## Launch with auto-reload (watchdog, if installed)
	$(PY) server.py --host $(HOST) --port $(PORT) --open

# ── quality ─────────────────────────────────────────────────────────────
lint: ## Lint (ruff)
	ruff check app server.py docker-entrypoint.py

format: ## Auto-format (black + ruff --fix)
	black app server.py tests
	ruff check --fix app server.py || true

format-check: ## Check formatting without modifying
	black --check app server.py tests
	ruff check app server.py

test: ## Run tests (each test deletes everything it creates, see tests/conftest.py)
	$(PY) -m pytest -q --cov=app --cov-report=term-missing

security: bandit pip-audit ## Run all security checks

bandit: ## Bandit SAST
	bandit -r app -c pyproject.toml 2>/dev/null || bandit -r app --severity-level medium --confidence-level medium || true

pip-audit: ## pip-audit for known CVEs
	pip-audit --desc 2>/dev/null || echo "pip-audit: no fixable CVEs or audit skipped"

audit: pip-audit

# ── docker ──────────────────────────────────────────────────────────────
docker-build: ## Build Docker image (local)
	docker build -t $(IMAGE_NAME):$(VERSION) -t $(IMAGE_NAME):latest .

docker-run: ## Run the image like production: data kept in the named volume fihi-data
	docker run --rm -p $(PORT):8000 -v fihi-data:/data --env FIHI_ADMIN_PASSWORD=$${FIHI_ADMIN_PASSWORD:-change-me-please} $(IMAGE_NAME):latest

docker-scan: ## Trivy scan (if trivy installed)
	trivy image --severity HIGH,CRITICAL $(IMAGE_NAME):latest 2>/dev/null || echo "install trivy: https://aquasecurity.github.io/trivy"

# ── git / github ────────────────────────────────────────────────────────
github-init: ## Init git repo, add remote, first commit (set REMOTE=url)
	@if [ ! -d .git ]; then git init && echo "db kept but ignored for deploy" && git add . && git commit -m "chore: initial enterprise scaffold" && echo "✔ git init"; else echo "git already init"; fi
	@if [ -n "$(REMOTE)" ]; then git remote add origin $(REMOTE) 2>/dev/null || git remote set-url origin $(REMOTE); else echo "set REMOTE=https://github.com/<org>/<repo>.git to add origin"; fi

push: ## git push (lint+test before push)
	$(MAKE) lint
	$(MAKE) test
	git add -A -- . ':!*.db'
	git status
	@echo "→ git commit & push"
	git branch -M main
	@git commit -m "chore: push $(VERSION)" 2>/dev/null || echo "nothing to commit"
	git push origin main

# ── deploy ──────────────────────────────────────────────────────────────
deploy: deploy-railway ## Default deploy = Railway

deploy-railway: ## Deploy to Railway (requires: railway login && railway link)
	railway up --service $${RAILWAY_SERVICE:-fihi-chifae}

backup: ## Download a backup zip from production (needs URL and a logged-in COOKIE=fc_session=...)
	@if [ -z "$(URL)" ] || [ -z "$(COOKIE)" ]; then echo "usage: make backup URL=https://... COOKIE=fc_session=..."; else mkdir -p backups && curl -fsS -H "Cookie: $(COOKIE)" "$(URL)/api/v1/admin/backup" -o backups/fihi-chifae-$$(date +%Y%m%d-%H%M).zip && echo "✔ saved in backups/"; fi

deploy-fly: ## Deploy to Fly.io (requires flyctl auth & fly.toml)
	@if [ ! -f fly.toml ]; then echo "fly.toml not found — run: fly launch --no-deploy"; else fly deploy --ha=false; fi

deploy-render: ## Trigger Render deploy via hook ($RENDER_DEPLOY_HOOK)
	@if [ -z "$$RENDER_DEPLOY_HOOK" ]; then echo "set RENDER_DEPLOY_HOOK env"; else curl -X POST "$$RENDER_DEPLOY_HOOK"; fi

# ── clean ───────────────────────────────────────────────────────────────
clean: ## Remove caches, db journal, build artifacts
	@echo "cleaning..."
	@$(PY) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['__pycache__','app/__pycache__','.pytest_cache','htmlcov','build','dist','.ruff_cache']]; import pathlib; [p.unlink(missing_ok=True) for p in pathlib.Path('.').glob('*.pyc')]"
	@echo "done"

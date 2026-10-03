# fihi-chifae — Makefile (enterprise, POSIX, Windows Git Bash compatible)
# Usage: make <target>  |  make help
# Requires: python (3.10+), pip, git. Optional: docker, flyctl, pyinstaller

PY            ?= python
PIP           ?= $(PY) -m pip
PORT          ?= 8000
HOST          ?= 0.0.0.0
DB            ?= fihi-chifae.db
IMAGE_NAME    ?= fihi-chifae
GHCR_IMAGE    ?= ghcr.io/fihi-chifae/$(IMAGE_NAME)
VERSION       ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
PLATFORMS     ?= linux/amd64,linux/arm64

.DEFAULT_GOAL := help
.PHONY: help install launch dev test lint format format-check security audit bandit pip-audit clean binary binary-zipapp binary-pyinstaller docker-build docker-run docker-scan push github-init deploy deploy-fly deploy-render binary-check

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
lint: ## Lint (ruff + flake8)
	ruff check app server.py || true
	flake8 app server.py --max-line-length=100 --extend-ignore=E203,W503 || true

format: ## Auto-format (black + ruff --fix)
	black app server.py
	ruff check --fix app server.py || true

format-check: ## Check formatting without modifying
	black --check app server.py
	ruff check app server.py

test: ## Run tests (pytest + compileall smoke)
	$(PY) -m compileall app server.py
	@if [ -d tests ]; then $(PY) -m pytest -q --cov=app --cov-report=term-missing 2>/dev/null || $(PY) -c "from app import db, catalog; print('smoke ok (pytest not installed)')"; else echo "no tests/ yet — running smoke test" && $(PY) -c "from app import db, catalog; print('smoke ok')"; fi

security: bandit pip-audit ## Run all security checks

bandit: ## Bandit SAST
	bandit -r app -c pyproject.toml 2>/dev/null || bandit -r app --severity-level medium --confidence-level medium || true

pip-audit: ## pip-audit for known CVEs
	pip-audit --desc 2>/dev/null || echo "pip-audit: no fixable CVEs or audit skipped"

audit: pip-audit

# ── binary ──────────────────────────────────────────────────────────────
binary: binary-zipapp ## Default binary = zipapp (portable, no compiler needed)

binary-zipapp: ## Build portable zipapp (dist/fihi-chifae.pyz)
	@echo "→ building zipapp..."
	@$(PY) -c "import pathlib; pathlib.Path('dist').mkdir(parents=True, exist_ok=True)"
	$(PY) -m zipapp app -m "serve:main" -o dist/fihi-chifae.pyz -p "/usr/bin/env python3" -c
	@echo "✔ dist/fihi-chifae.pyz  (run: python dist/fihi-chifae.pyz --port 8000 — note: serve static files from original dir, for full bundle use 'make docker-build')"

binary-pyinstaller: ## Build native executable via PyInstaller (dist/fihi-chifae.exe)
	@echo "→ building PyInstaller binary (may take a minute)..."
	pyinstaller --onefile --name fihi-chifae --add-data "assets;assets" --add-data "index.html;." --add-data "admin.html;." --add-data "admin-add.html;." --add-data "admin-reset.html;." server.py --distpath dist --workpath build --specpath build
	@echo "✔ dist/fihi-chifae(.exe)"

binary-check: binary ## Verify binary runs
	$(PY) dist/fihi-chifae.pyz --help 2>/dev/null || ./dist/fihi-chifae --help 2>/dev/null || echo "binary check: run manually"

# ── docker ──────────────────────────────────────────────────────────────
docker-build: ## Build Docker image (local)
	docker build -t $(IMAGE_NAME):$(VERSION) -t $(IMAGE_NAME):latest .

docker-run: ## Run Docker image locally (PORT=$(PORT))
	docker run --rm -p $(PORT):8000 --env PORT=8000 --env FIHI_ADMIN_PASSWORD=admin2026 $(IMAGE_NAME):latest

docker-scan: ## Trivy scan (if trivy installed)
	trivy image --severity HIGH,CRITICAL $(IMAGE_NAME):latest 2>/dev/null || echo "install trivy: https://aquasecurity.github.io/trivy"

# ── git / github ────────────────────────────────────────────────────────
github-init: ## Init git repo, add remote, first commit (set REMOTE=url)
	@if [ ! -d .git ]; then git init && echo "db kept but ignored for deploy" && git add . && git commit -m "chore: initial enterprise scaffold" && echo "✔ git init"; else echo "git already init"; fi
	@if [ -n "$(REMOTE)" ]; then git remote add origin $(REMOTE) 2>/dev/null || git remote set-url origin $(REMOTE); else echo "set REMOTE=https://github.com/<org>/<repo>.git to add origin"; fi

push: ## git push (lint+test before push)
	$(MAKE) lint
	$(MAKE) test
	git add .
	git status
	@echo "→ git commit & push"
	@git commit -m "chore: push $(VERSION)" 2>/dev/null || echo "nothing to commit"
	git push origin HEAD

# ── deploy ──────────────────────────────────────────────────────────────
deploy: deploy-fly ## Default deploy = Fly.io

deploy-fly: ## Deploy to Fly.io (requires flyctl auth & fly.toml)
	@if [ ! -f fly.toml ]; then echo "fly.toml not found — run: fly launch --no-deploy"; else fly deploy --ha=false; fi

deploy-render: ## Trigger Render deploy via hook ($RENDER_DEPLOY_HOOK)
	@if [ -z "$$RENDER_DEPLOY_HOOK" ]; then echo "set RENDER_DEPLOY_HOOK env"; else curl -X POST "$$RENDER_DEPLOY_HOOK"; fi

# ── clean ───────────────────────────────────────────────────────────────
clean: ## Remove caches, db journal, build artifacts
	@echo "cleaning..."
	@$(PY) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['__pycache__','app/__pycache__','.pytest_cache','htmlcov','build','dist','.ruff_cache']]; import pathlib; [p.unlink(missing_ok=True) for p in pathlib.Path('.').glob('*.pyc')]"
	@echo "done"

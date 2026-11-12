VENV ?= backend/.venv
PY := $(VENV)/bin/python

.PHONY: install test lint api simulate web up down tf-validate

install: ## install backend and frontend dependencies
	python3 -m venv $(VENV)
	$(PY) -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

test: ## run backend and frontend tests
	cd backend && ../$(PY) -m pytest --cov
	cd frontend && npm test

lint: ## ruff + type check
	cd backend && ../$(VENV)/bin/ruff check . && ../$(VENV)/bin/ruff format --check .
	cd frontend && npm run typecheck

api: ## run the API locally on :8000 (SQLite)
	cd backend && ../$(VENV)/bin/uvicorn app.main:create_app --factory --reload --port 8000

simulate: ## load 60 min of history, then stream live traffic with a CDN incident
	cd backend && ../$(PY) -m simulator backfill --minutes 60 && \
	  ../$(PY) -m simulator --incident-cdn fastly --incident-after 120 live --rate 5

web: ## run the dashboard dev server on :5173 (proxies to :8000)
	cd frontend && npm run dev

up: ## full stack in Docker
	docker compose up --build

down:
	docker compose down -v

tf-validate:
	cd infra/terraform && terraform fmt -check && terraform init -backend=false && terraform validate

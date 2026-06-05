# Cortex — Makefile
# All common developer and ops commands in one place.
# Usage: make <target>

.PHONY: help dev prod down logs shell db-shell test lint migrate deploy clean

# ─────────────────────────────────────────────────────────────────────────────
DOCKER_COMPOSE = docker compose
API_SERVICE    = api
WORKER_SERVICE = worker

# ─────────────────────────────────────────────────────────────────────────────
help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Local development ────────────────────────────────────────────────────────
dev:            ## Start full dev stack (detached)
	@cp -n .env.example .env 2>/dev/null || true
	$(DOCKER_COMPOSE) up -d --build
	@echo "\n✅ Stack running:"
	@echo "   API:      http://localhost:8000/api/docs"
	@echo "   Flower:   http://localhost:5555"
	@echo "   Grafana:  http://localhost:3000"
	@echo "   Prometheus: http://localhost:9090"

down:           ## Stop all services
	$(DOCKER_COMPOSE) down

restart:        ## Restart API and worker only
	$(DOCKER_COMPOSE) restart $(API_SERVICE) $(WORKER_SERVICE)

logs:           ## Tail logs for all services
	$(DOCKER_COMPOSE) logs -f

logs-api:       ## Tail API logs only
	$(DOCKER_COMPOSE) logs -f $(API_SERVICE)

logs-worker:    ## Tail worker logs only
	$(DOCKER_COMPOSE) logs -f $(WORKER_SERVICE)

# ─── Shells ───────────────────────────────────────────────────────────────────
shell:          ## Shell into API container
	$(DOCKER_COMPOSE) exec $(API_SERVICE) bash

db-shell:       ## psql into Postgres
	$(DOCKER_COMPOSE) exec postgres psql -U cortex -d cortex_db

redis-shell:    ## redis-cli into Redis
	$(DOCKER_COMPOSE) exec redis redis-cli -a $${REDIS_PASSWORD:-redispass}

# ─── Database ─────────────────────────────────────────────────────────────────
migrate:        ## Run Alembic migrations
	$(DOCKER_COMPOSE) exec $(API_SERVICE) alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create MSG="add user table")
	$(DOCKER_COMPOSE) exec $(API_SERVICE) alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Show migration history
	$(DOCKER_COMPOSE) exec $(API_SERVICE) alembic history --verbose

migrate-down:   ## Rollback last migration
	$(DOCKER_COMPOSE) exec $(API_SERVICE) alembic downgrade -1

db-backup:      ## Dump Postgres to ./backups/
	@mkdir -p backups
	$(DOCKER_COMPOSE) exec postgres pg_dump -U cortex cortex_db \
		| gzip > backups/cortex_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "✅ Backup saved to backups/"

# ─── Testing ──────────────────────────────────────────────────────────────────
test:           ## Run full test suite
	$(DOCKER_COMPOSE) exec $(API_SERVICE) \
		pytest tests/ -v --tb=short --cov=api --cov=workers --cov-report=term-missing

test-fast:      ## Run tests excluding slow pipeline tests
	$(DOCKER_COMPOSE) exec $(API_SERVICE) \
		pytest tests/ -v --tb=short -m "not slow"

test-e2e:       ## Run E2E integration tests only
	$(DOCKER_COMPOSE) exec $(API_SERVICE) \
		pytest tests/test_e2e.py -v -s

probe:          ## Run the debug probe against local stack
	$(DOCKER_COMPOSE) exec $(API_SERVICE) python debug_probe.py

# ─── Code quality ─────────────────────────────────────────────────────────────
lint:           ## Run flake8 + mypy
	$(DOCKER_COMPOSE) exec $(API_SERVICE) flake8 api/ workers/ --max-line-length=100
	$(DOCKER_COMPOSE) exec $(API_SERVICE) mypy api/ workers/ --ignore-missing-imports

format:         ## Auto-format with black + isort
	$(DOCKER_COMPOSE) exec $(API_SERVICE) black api/ workers/ tests/
	$(DOCKER_COMPOSE) exec $(API_SERVICE) isort api/ workers/ tests/

# ─── CI/CD ────────────────────────────────────────────────────────────────────
ci:             ## Full CI pipeline (lint + test + probe)
	@make lint
	@make test
	@make probe

# ─── Production ───────────────────────────────────────────────────────────────
build:          ## Build production Docker image
	docker build -t cortex-api:$(shell git rev-parse --short HEAD) \
		--target runtime .

push:           ## Push image to registry (set REGISTRY env var)
	docker tag cortex-api:$(shell git rev-parse --short HEAD) \
		$(REGISTRY)/cortex-api:$(shell git rev-parse --short HEAD)
	docker push $(REGISTRY)/cortex-api:$(shell git rev-parse --short HEAD)

deploy:         ## Deploy to production (Railway/Render webhook)
	@echo "Triggering deployment..."
	curl -X POST $(DEPLOY_WEBHOOK_URL)

# ─── Cleanup ──────────────────────────────────────────────────────────────────
clean:          ## Remove containers, volumes, images
	$(DOCKER_COMPOSE) down -v --remove-orphans
	docker system prune -f

clean-cache:    ## Flush Redis cache (keep jobs)
	$(DOCKER_COMPOSE) exec redis redis-cli -a $${REDIS_PASSWORD:-redispass} \
		--scan --pattern "inspection:result:*" | xargs redis-cli DEL
	@echo "✅ Result cache flushed"

# LibreChat Deployment Makefile for Bruce BEM
# IMPORTANT: Uses docker-compose.dev.yml to build from local source (includes auto-login)
# Do NOT use plain docker-compose.yml - that uses official image without customizations

.DEFAULT_GOAL := help

.PHONY: help deploy start stop restart logs status clean

# Main deployment (builds from local source)
deploy: ## Build and deploy LibreChat with auto-login support
	docker compose -f docker-compose.dev.yml up -d --build

# Service management
start: ## Start services (without rebuild)
	docker compose -f docker-compose.dev.yml up -d

stop: ## Stop all containers
	docker compose -f docker-compose.dev.yml down

restart: ## Restart services (picks up config changes, NOT code changes)
	docker compose -f docker-compose.dev.yml restart

logs: ## Follow container logs
	docker compose -f docker-compose.dev.yml logs -f

logs-api: ## Follow only API container logs
	docker compose -f docker-compose.dev.yml logs -f api

# Utility
status: ## Show running containers
	docker ps --filter "name=LibreChat" --filter "name=chat-" --filter "name=vectordb" --filter "name=rag_api"

clean: ## Stop and remove all containers and volumes
	docker compose -f docker-compose.dev.yml down -v --remove-orphans

help:
	@echo "============================================"
	@echo "LibreChat Deployment Commands (Bruce BEM)"
	@echo "============================================"
	@echo ""
	@echo "  make deploy   - Build and deploy (RECOMMENDED)"
	@echo "  make start    - Start without rebuild"
	@echo "  make stop     - Stop all containers"
	@echo "  make restart  - Full restart with rebuild"
	@echo "  make logs     - Follow all logs"
	@echo "  make logs-api - Follow API logs only"
	@echo ""
	@echo "  make status   - Show running containers"
	@echo "  make clean    - Remove containers and volumes"
	@echo ""
	@echo "============================================"
	@echo "IMPORTANT: After changing .env, run:"
	@echo "  make restart"
	@echo "(Simple restart won't pick up env changes)"
	@echo "============================================"

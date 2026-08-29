SHELL := /bin/bash

APP_SERVICE ?= fantasy-football-backend
HEALTH_URL ?= http://127.0.0.1:8000/health

.PHONY: deploy rollback restart logs status backup restore help

help:
	@./deploy/deploy.sh help

deploy:
	@APP_SERVICE=$(APP_SERVICE) HEALTH_URL=$(HEALTH_URL) ./deploy/deploy.sh deploy

rollback:
	@APP_SERVICE=$(APP_SERVICE) HEALTH_URL=$(HEALTH_URL) ./deploy/deploy.sh rollback

restart:
	@APP_SERVICE=$(APP_SERVICE) HEALTH_URL=$(HEALTH_URL) ./deploy/deploy.sh restart

logs:
	@APP_SERVICE=$(APP_SERVICE) ./deploy/deploy.sh logs

status:
	@APP_SERVICE=$(APP_SERVICE) HEALTH_URL=$(HEALTH_URL) ./deploy/deploy.sh status

backup:
	@APP_SERVICE=$(APP_SERVICE) ./deploy/deploy.sh backup

restore:
	@if [ -z "$(RESTORE_FILE)" ]; then \
		echo "Usage: make restore RESTORE_FILE=/path/to/archive" >&2; \
		exit 1; \
	fi
	@APP_SERVICE=$(APP_SERVICE) ./deploy/deploy.sh restore "$(RESTORE_FILE)"

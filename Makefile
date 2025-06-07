.PHONY: help install setup run-api run-worker run-beat test clean docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  install      - Install dependencies"
	@echo "  setup        - Setup database and create tables"
	@echo "  run-api      - Run FastAPI server"
	@echo "  run-worker   - Run Celery worker"
	@echo "  run-beat     - Run Celery beat scheduler"
	@echo "  test         - Run simple test"
	@echo "  docker-up    - Start Redis and PostgreSQL"
	@echo "  docker-down  - Stop Docker services"
	@echo "  clean        - Clean cache files"

install:
	pip install -r requirements.txt

setup:
	@echo "Setting up database..."
	python scripts/init_db.py
	@echo "Database setup complete!"

run-api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	celery -A app.tasks.celery_tasks worker --loglevel=info --pool=solo

run-beat:
	celery -A app.tasks.celery_tasks beat --loglevel=info

test:
	python simple_test.py

docker-up:
	docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	@echo "Services started!"

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -f celerybeat-schedule*
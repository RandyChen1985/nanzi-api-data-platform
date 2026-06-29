"""Gunicorn configuration for production deployment."""
import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('API_SERVICE_PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", max(2, multiprocessing.cpu_count())))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Scheduler runs in all workers but jobs deduplicate via Redis lock
raw_env = [
    f"ENABLE_SCHEDULER={os.getenv('ENABLE_SCHEDULER', '1')}",
]

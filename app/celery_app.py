# app/celery_app.py
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    __name__,
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_BACKEND_URL", "redis://localhost:6379/0"),
    include=["tasks.pdf_task"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,      # important for large memory tasks
    task_acks_late=True,               # prevent losing tasks if worker killed
    result_expires=3600,               # clean old results after 1h
    task_time_limit=900,               # kill tasks >15 min
    task_soft_time_limit=840,
    task_track_started=True,
)
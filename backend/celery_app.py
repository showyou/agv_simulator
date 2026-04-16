from celery import Celery
from backend import config

celery_app = Celery(
    "distribution_sim",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
)

# タスクを自動検出
celery_app.autodiscover_tasks(["backend.agents"])

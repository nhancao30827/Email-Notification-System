from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "email_distribution_system",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.features.email_deliveries.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

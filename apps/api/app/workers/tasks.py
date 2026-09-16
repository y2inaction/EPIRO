"""Celery tasks for background jobs."""
from celery import Celery
from app.config import settings

app = Celery(
    'epiro',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
)


@app.task(bind=True)
def sample_task(self):
    """Sample background task."""
    return "Task completed"


@app.task(bind=True)
def process_evidence(self, evidence_id: str):
    """Process evidence after creation."""
    return f"Evidence {evidence_id} processed"


@app.task(bind=True)
def generate_report(self, report_type: str):
    """Generate report asynchronously."""
    return f"Report type {report_type} generated"

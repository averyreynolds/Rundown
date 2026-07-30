"""Scheduled background jobs: periodic cache refresh and a daily snapshot write.

`AsyncIOScheduler`, started/stopped in the FastAPI lifespan -- not
Celery/RQ -- per the plan's Key Technical Decisions: no broker or
separate worker process needed for a single-user, single-process app.
Assumes `uvicorn --workers 1`; a multi-worker deployment would create N
independent schedulers each refreshing the cache redundantly.
"""

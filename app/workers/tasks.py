"""
Celery task definitions for the pitch deck pipeline.
Each Excel row becomes one task processed sequentially.
"""
import asyncio
import json
import time
import traceback

from celery import Celery
import redis

from app.config import settings
from app.models import ProspectRow, RowResult, RowStatus

# Initialize Celery with Redis backend
celery_app = Celery(
    "pitch_deck_creator",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_concurrency=1,  # Solo pool; one task at a time (API rate limits)
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,  # 10 minute hard limit per task
    task_soft_time_limit=540,  # 9 minute soft limit
)

# Redis client for status tracking
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def _update_row_status(job_id: str, row_index: int, status: RowStatus, **extra):
    """Update the status of a specific row in Redis."""
    key = f"job:{job_id}:row:{row_index}"
    data = {"status": status.value, **extra}
    redis_client.hset(key, mapping={k: str(v) for k, v in data.items()})

    # Also update the job-level progress
    job_key = f"job:{job_id}"
    if status == RowStatus.COMPLETE:
        redis_client.hincrby(job_key, "completed", 1)
    elif status == RowStatus.FAILED:
        redis_client.hincrby(job_key, "failed", 1)


def _run_async(coro):
    """Run an async function from a sync context (background thread)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def process_prospect(self, prospect_data: dict, job_id: str):
    """
    Main pipeline task: Research → Content Gen → Gamma Deck → Return URL.
    Runs synchronously within Celery worker.
    """
    from app.services.researcher import research_company
    from app.services.content_generator import generate_pitch
    from app.services.gamma_client import create_presentation

    prospect = ProspectRow(**prospect_data)
    row_index = prospect.row_index

    try:
        # Step 1: Research
        _update_row_status(job_id, row_index, RowStatus.RESEARCHING)
        research = _run_async(research_company(prospect))
        time.sleep(2)  # Rate limit buffer between API calls

        # Step 2: Content Generation
        _update_row_status(job_id, row_index, RowStatus.GENERATING_CONTENT)
        pitch_content = _run_async(generate_pitch(prospect, research))
        time.sleep(2)

        # Step 3: Gamma Deck Creation
        _update_row_status(job_id, row_index, RowStatus.CREATING_DECK)
        gamma_result = _run_async(create_presentation(pitch_content))

        # Step 4: Success
        _update_row_status(
            job_id,
            row_index,
            RowStatus.COMPLETE,
            deck_url=gamma_result.url,
            pptx_url=gamma_result.pptx_url,
        )

        result = RowResult(
            row_index=row_index,
            company_name=prospect.company_name,
            status=RowStatus.COMPLETE,
            deck_url=gamma_result.url,
            pptx_url=gamma_result.pptx_url,
        )
        return result.model_dump()

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        _update_row_status(
            job_id,
            row_index,
            RowStatus.FAILED,
            error=error_msg,
        )
        traceback.print_exc()

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return RowResult(
            row_index=row_index,
            company_name=prospect.company_name,
            status=RowStatus.FAILED,
            error=error_msg,
        ).model_dump()


@celery_app.task
def finalize_job(results: list, job_id: str, original_file_path: str):
    """
    After all row tasks complete, write deck URLs back to Excel.
    This is the chord callback that runs after all process_prospect tasks finish.
    """
    from app.services.excel_parser import write_results

    row_results = [RowResult(**r) for r in results if r]

    # Write output Excel
    output_path = write_results(original_file_path, row_results, settings.output_dir)

    # Update job status in Redis
    job_key = f"job:{job_id}"
    redis_client.hset(job_key, mapping={
        "status": "complete",
        "output_file": output_path,
    })

    return {"job_id": job_id, "output_file": output_path}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def process_single_prospect(self, prospect_data: dict, job_id: str):
    """
    Process a single prospect: Research → Content Gen → Gamma Deck → Return URL.
    Same pipeline as process_prospect but for single client form.
    """
    from app.services.researcher import research_company
    from app.services.content_generator import generate_pitch
    from app.services.gamma_client import create_presentation

    prospect = ProspectRow(**prospect_data)
    row_index = 0  # Single client always uses row 0

    try:
        # Step 1: Research
        _update_row_status(job_id, row_index, RowStatus.RESEARCHING)
        research = _run_async(research_company(prospect))
        time.sleep(2)

        # Step 2: Content Generation
        _update_row_status(job_id, row_index, RowStatus.GENERATING_CONTENT)
        pitch_content = _run_async(generate_pitch(prospect, research))
        time.sleep(2)

        # Step 3: Gamma Deck Creation
        _update_row_status(job_id, row_index, RowStatus.CREATING_DECK)
        gamma_result = _run_async(create_presentation(pitch_content))

        # Step 4: Success
        _update_row_status(
            job_id,
            row_index,
            RowStatus.COMPLETE,
            deck_url=gamma_result.url,
            pptx_url=gamma_result.pptx_url,
        )

        # Update job status to complete
        job_key = f"job:{job_id}"
        redis_client.hset(job_key, mapping={
            "status": "complete",
            "completed": "1",
        })

        return RowResult(
            row_index=row_index,
            company_name=prospect.company_name,
            status=RowStatus.COMPLETE,
            deck_url=gamma_result.url,
            pptx_url=gamma_result.pptx_url,
        ).model_dump()

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        _update_row_status(
            job_id,
            row_index,
            RowStatus.FAILED,
            error=error_msg,
        )

        job_key = f"job:{job_id}"
        redis_client.hset(job_key, mapping={
            "status": "failed",
            "failed": "1",
        })

        traceback.print_exc()

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return RowResult(
            row_index=row_index,
            company_name=prospect.company_name,
            status=RowStatus.FAILED,
            error=error_msg,
        ).model_dump()

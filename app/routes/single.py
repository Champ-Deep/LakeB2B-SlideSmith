"""
Single client route – handles individual prospect processing.
"""
import asyncio
import uuid
from functools import partial

import redis
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models import SingleProspect, RowStatus
from app.workers.tasks import process_single_prospect

router = APIRouter()
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

_STAGE_PROGRESS = {
    RowStatus.QUEUED.value: 0,
    RowStatus.RESEARCHING.value: 25,
    RowStatus.GENERATING_CONTENT.value: 50,
    RowStatus.CREATING_DECK.value: 75,
    RowStatus.COMPLETE.value: 100,
    RowStatus.FAILED.value: 100,
}


@router.post("/single")
async def create_single_prospect(data: SingleProspect):
    """
    Process a single client through the pitch deck pipeline.
    """
    if not data.client_name or not data.company or not data.role:
        raise HTTPException(
            status_code=400,
            detail="Client name, company, and role are required.",
        )

    job_id = str(uuid.uuid4())[:8]

    redis_client.hset(f"job:{job_id}", mapping={
        "status": "processing",
        "total_rows": "1",
        "completed": "0",
        "failed": "0",
        "original_file": "",
        "output_file": "",
        "is_single": "true",
    })

    redis_client.hset(f"job:{job_id}:row:0", mapping={
        "company_name": data.company,
        "status": RowStatus.QUEUED.value,
        "deck_url": "",
        "pptx_url": "",
        "error": "",
    })

    prospect_data = {
        "row_index": 0,
        "company_name": data.company,
        "industry": "",
        "website_url": "",
        "contact_name": data.client_name,
        "contact_title": data.role,
        "extra_context": _build_extra_context(data),
    }

    # Run pipeline in background thread (no separate Celery worker needed)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        partial(process_single_prospect.apply, args=[prospect_data, job_id]),
    )

    return {
        "job_id": job_id,
        "company_name": data.company,
        "status": "processing",
        "message": "Processing pitch deck. Track progress at /single/status/" + job_id,
    }


@router.get("/single/status/{job_id}")
async def get_single_status(job_id: str):
    """
    Get status for a single client processing job.
    """
    job_key = f"job:{job_id}"
    row_key = f"job:{job_id}:row:0"

    job_data = redis_client.hgetall(job_key)
    row_data = redis_client.hgetall(row_key)

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    status = job_data.get("status", "pending")
    completed = int(job_data.get("completed", 0))
    failed = int(job_data.get("failed", 0))

    return {
        "job_id": job_id,
        "company_name": row_data.get("company_name", ""),
        "status": status,
        "completed": completed,
        "failed": failed,
        "progress_percent": _STAGE_PROGRESS.get(row_data.get("status", RowStatus.QUEUED.value), 0),
        "current_stage": row_data.get("status", RowStatus.QUEUED.value),
        "deck_url": row_data.get("deck_url", ""),
        "pptx_url": row_data.get("pptx_url", ""),
        "error": row_data.get("error", ""),
    }


def _build_extra_context(data: SingleProspect) -> str:
    """Build extra context string from optional fields."""
    parts = []
    if data.linkedin_url:
        parts.append(f"LinkedIn: {data.linkedin_url}")
    if data.email:
        parts.append(f"Email: {data.email}")
    if data.phone:
        parts.append(f"Phone: {data.phone}")
    if data.notes:
        parts.append(f"Notes: {data.notes}")
    return " | ".join(parts)

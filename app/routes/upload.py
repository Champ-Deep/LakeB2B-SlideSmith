"""
Upload route – handles Excel file upload and job creation.
"""
import os
import uuid
from pathlib import Path

import redis
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import settings
from app.models import RowStatus
from app.services.excel_parser import parse_excel
from app.workers.tasks import process_prospect, finalize_job, celery_app

from celery import chord

router = APIRouter()
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload an Excel file of prospects.
    Parses the file, creates a job, and queues each row for processing.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Please upload an Excel file (.xlsx or .xls)",
        )

    # Save uploaded file
    os.makedirs(settings.upload_dir, exist_ok=True)
    job_id = str(uuid.uuid4())[:8]
    file_ext = Path(file.filename).suffix
    saved_filename = f"{job_id}_{file.filename}"
    saved_path = os.path.join(settings.upload_dir, saved_filename)

    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Parse Excel
    try:
        prospects = parse_excel(saved_path)
    except ValueError as e:
        os.remove(saved_path)
        raise HTTPException(status_code=400, detail=str(e))

    if len(prospects) > settings.max_rows_per_upload:
        os.remove(saved_path)
        raise HTTPException(
            status_code=400,
            detail=f"Too many rows ({len(prospects)}). Maximum is {settings.max_rows_per_upload}.",
        )

    if not prospects:
        os.remove(saved_path)
        raise HTTPException(status_code=400, detail="No valid prospect rows found in the Excel file.")

    # Initialize job status in Redis
    job_key = f"job:{job_id}"
    redis_client.hset(job_key, mapping={
        "status": "processing",
        "total_rows": str(len(prospects)),
        "completed": "0",
        "failed": "0",
        "original_file": saved_path,
        "output_file": "",
    })

    # Initialize per-row status
    for prospect in prospects:
        row_key = f"job:{job_id}:row:{prospect.row_index}"
        redis_client.hset(row_key, mapping={
            "company_name": prospect.company_name,
            "status": RowStatus.QUEUED.value,
            "deck_url": "",
            "pptx_url": "",
            "error": "",
        })

    # Queue tasks using Celery chord (all rows → finalize)
    row_tasks = [
        process_prospect.s(prospect.model_dump(), job_id)
        for prospect in prospects
    ]

    callback = finalize_job.s(job_id, saved_path)
    chord(row_tasks)(callback)

    return {
        "job_id": job_id,
        "total_rows": len(prospects),
        "status": "processing",
        "message": f"Processing {len(prospects)} prospects. Track progress at /status/{job_id}",
    }
